import asyncio
from core.db_async import AsyncDatabase
from core.env import Environment
# Import Models to register them
from addons.base.models.res_users import ResUsers
from addons.base.models.res_partner import ResPartner
from addons.base.models.res_groups import ResGroups

async def test_native_orm():
    print("Testing Native SQL ORM...")
    db = AsyncDatabase()
    await db.initialize()
    
    async with db.acquire() as cr:
        # Ensure tables exist (for test safety)
        await ResPartner._auto_init(cr)
        await ResUsers._auto_init(cr)
        
        env = Environment(cr, uid=1)
        User = env['res.users']
        
        # Test 1: Search (Triggers Native SQL in search, _apply_ir_rules, check_access_rights)
        print("Searching...")
        users = await User.search([], limit=1)
        print(f"Found user IDs: {users.ids}")
        
        # Test 2: Create (Triggers Native SQL in create)
        print("Creating User...")
        # Create unique login to avoid constraint error
        import time
        suffix = int(time.time())
        new_user = await User.create({
            'name': f'NativeSQL Test {suffix}',
            'login': f'native_sql_{suffix}',
            'password': '123'
        })
        print(f"Created ID: {new_user.id}")
        
        # Test 3: Read
        await new_user.read(['login'])
        print(f"Read Login: {new_user.login}")
        
        # Test 4: Write
        new_login = f'native_sql_upd_{suffix}'
        await new_user.write({'login': new_login})
        print("Updated.")
        
        await new_user.read(['login'])
        print(f"Verified Update: {new_user.login}")
        
        # Test 5: Unlink
        await new_user.unlink()
        print("Unlinked.")

if __name__ == "__main__":
    asyncio.run(test_native_orm())
