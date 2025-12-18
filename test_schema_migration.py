
import asyncio
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char
from core.env import Environment
from core.schema import SchemaManager

class MigDoc(Model):
    _name = 'mig.doc'
    name = Char()

Registry.register('mig.doc', MigDoc)

async def test_migration():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
        # 1. Clean Start
        await cr.execute("DROP TABLE IF EXISTS mig_doc CASCADE")
        
        # 2. Initial Create (Only 'name')
        await MigDoc._auto_init(cr)
        
        # Verify columns
        await cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'mig_doc'")
        cols = [r['column_name'] for r in cr.fetchall()]
        print(f"Initial Cols: {cols}")
        if 'name' in cols and 'new_col' not in cols:
            print("PASS: Initial state correct.")
        
        # 3. Modify Model (Add Field)
        # Dynamic Field Injection
        new_field = Char(string='New Col')
        MigDoc._fields['new_col'] = new_field
        new_field.name = 'new_col' # ORM usually sets this in metaclass, manual here
        new_field._sql_type = 'VARCHAR' # Manual setup usually done by Field
        
        # 4. Run Migration
        print("Running Schema Migration...")
        manager = SchemaManager(cr)
        await manager.sync_model(MigDoc)
        
        # 5. Verify New Column
        await cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'mig_doc'")
        cols_new = [r['column_name'] for r in cr.fetchall()]
        print(f"Post-Migration Cols: {cols_new}")
        
        if 'new_col' in cols_new:
            print("PASS: Column 'new_col' added successfully.")
        else:
            print("FAIL: Column missing.")

    await AsyncDatabase.close()

if __name__ == "__main__":
    asyncio.run(test_migration())
