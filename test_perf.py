import sys
import os
import asyncio
from core.db import Database
from core.env import Environment
# Fix Imports
sys.path.append(os.getcwd())
# Register Model
from addons.base.models.res_users import ResUsers

async def test_search_read():
    print("--- Testing search_read Optimization ---")
    
    # 1. Init (using core components)
    # We need to simulate server environment or reuse it
    # Easier: Use app's lifespan logic or just AsyncDatabase
    from core.db_async import AsyncDatabase
    await AsyncDatabase.initialize()
    
    # Manually acquire connection to create Env
    async with AsyncDatabase.get_pool().acquire() as conn:
         # Need cursor wrapper if Env expects it?
         # Env expects `cr`. AsyncDatabase.get_pool() returns asyncpg connection.
         # core/db_async.py has AsyncCursor wrapper? 
         # Or we can just pass connection if Env handles it?
         # Env expects `cr` with `execute`. Connection has `execute`.
         # But ORM uses `cr.fetchall`. Connection has `fetch`.
         # We need AsyncCursor wrapper.
         from core.db_async import AsyncCursor
         cursor = AsyncCursor(conn)
         
         env = Environment(cursor, uid=1)
         
         User = env['res.users']
         
         print("Calling search_read(['login', 'company_id'])...")
         # This should trigger OPTIMIZED path
         res = await User.search_read([], ['login', 'company_id'])
         print(f"Result: {len(res)} records")
         if res:
             print(f"Sample: {res[0]}")
             # Check if company_id is tuple (id, name)
             if 'company_id' in res[0] and isinstance(res[0]['company_id'], (tuple, list)):
                 print("SUCCESS: M2O joined correctly.")
             elif 'company_id' in res[0] and res[0]['company_id'] is False:
                 print("SUCCESS: M2O joined (Found None).")
             else:
                 print(f"FAILURE: company_id format wrong: {res[0].get('company_id')}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_search_read())
