
import asyncio
import os
import sys

# Ensure root
sys.path.append(os.getcwd())

from core.db_async import AsyncDatabase
from core.env import Environment
from core.registry import Registry

# Load Models
# Import core models (ir.*)
import core.models # Trigger registration

from addons.base.models.res_partner import ResPartner
from addons.base.models.res_users import ResUsers

async def test_orm_flow():
    print("Initializing AsyncDatabase...")
    await AsyncDatabase.initialize()
    
    try:
        async with AsyncDatabase.acquire() as cr:
            # 1. Setup / Migration
            await Registry.setup_models(cr)
            
            # 2. CRUD Test
            env = Environment(cr, uid=1)
            
            # Create
            print("Creating User...")
            user = await env['res.users'].create({
                'login': 'async_test_user',
                'password': 'safe_password',
                'name': 'Test User' # ResUsers inherits? No, ResUsers has related partner usually but let's check definition. Assumed simplistic.
            })
            print(f"User Created: {user.id}")
            
            # Search
            users = await env['res.users'].search([('login', '=', 'async_test_user')])
            print(f"Search Found: {len(users)}")
            
            # Read
            data = await users.read(['login', 'password'])
            print(f"Read Data: {data}")
            
            # Write
            await users.write({'login': 'async_test_updated'})
            
            # Verify Update
            updated = await env['res.users'].search([('login', '=', 'async_test_updated')])
            print(f"Update Verified: {len(updated)}")
            
            # Unlink
            await users.unlink()
            print("User Deleted")
            
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await AsyncDatabase.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_orm_flow())
