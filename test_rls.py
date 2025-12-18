
import asyncio
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char, Integer
from core.env import Environment

# Mock Model for RLS
class RlsDoc(Model):
    _name = 'rls.doc'
    name = Char()
    user_id = Integer() # simulating Many2one to res.users simplified

Registry.register('rls.doc', RlsDoc)

async def test_rls():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
        # 1. Setup Table
        await cr.execute("DROP TABLE IF EXISTS rls_doc CASCADE")
        await RlsDoc._auto_init(cr)
        
        # 2. Enable RLS
        print("Enabling RLS on rls_doc...")
        await cr.execute('ALTER TABLE "rls_doc" ENABLE ROW LEVEL SECURITY')
        
        # 3. Create Policy
        # Policy: User can only see rows where user_id = app.current_uid
        print("Creating RLS Policy...")
        policy_sql = """
        CREATE POLICY "user_own_docs" ON "rls_doc"
        FOR ALL
        TO PUBLIC
        USING (user_id = current_setting('app.current_uid')::int)
        """
        await cr.execute(policy_sql)
        
        # 4. Create Data
        await cr.execute('ALTER TABLE "rls_doc" FORCE ROW LEVEL SECURITY')
        
        # Insert for User 1
        await cr.execute("SET LOCAL app.current_uid = '1'")
        await cr.execute("INSERT INTO rls_doc (name, user_id) VALUES ('Doc User 1', 1)")
        
        # Insert for User 2
        await cr.execute("SET LOCAL app.current_uid = '2'")
        await cr.execute("INSERT INTO rls_doc (name, user_id) VALUES ('Doc User 2', 2)")
        
        # 4b. Setup Test Role (Non-Superuser)
        try:
             await cr.execute("CREATE ROLE rls_tester NOLOGIN")
        except:
             pass # Exists
        
        await cr.execute('GRANT ALL ON "rls_doc" TO rls_tester')
        await cr.execute('GRANT USAGE ON SCHEMA public TO rls_tester') # Ensure access
        
        # 5. Verify Visibility for User 1
        await cr.execute("SET ROLE rls_tester") # Switch to non-superuser
        await cr.execute("SET LOCAL app.current_uid = '1'")
        await cr.execute("SELECT * FROM rls_doc")
        rows = cr.fetchall()
        print(f"User 1 sees {len(rows)} docs: {[r['name'] for r in rows]}")
        
        if len(rows) == 1 and rows[0]['name'] == 'Doc User 1':
            print("PASS: User 1 sees strictly their own docs.")
        else:
            print(f"FAIL: User 1 saw {len(rows)} records.")
            
        # 6. Verify Visibility for User 2
        await cr.execute("SET LOCAL app.current_uid = '2'")
        await cr.execute("SELECT * FROM rls_doc")
        rows = cr.fetchall()
        print(f"User 2 sees {len(rows)} docs: {[r['name'] for r in rows]}")
        
        if len(rows) == 1 and rows[0]['name'] == 'Doc User 2':
             print("PASS: User 2 sees strictly their own docs.")
        else:
             print(f"FAIL: User 2 saw {len(rows)} records.")
             
        # 7. Unset Context
        await cr.execute("SET LOCAL app.current_uid = '999'")
        await cr.execute("SELECT * FROM rls_doc")
        rows = cr.fetchall()
        print(f"User 999 sees {len(rows)} docs")
        
        if len(rows) == 0:
             print("PASS: User 999 sees nothing.")
        else:
             print("FAIL: Leakage to unknown user.")
             
        # Cleanup
        await cr.execute("RESET ROLE") # Back to Superuser to drop?
        # Note: Transaction rollback might handle it, but RESET is safer.

    await AsyncDatabase.close()

if __name__ == "__main__":
    asyncio.run(test_rls())
