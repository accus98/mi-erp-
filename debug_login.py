
import asyncio
from core.db_async import AsyncDatabase
import os
import sys

# Load Modules Stub
def load_modules():
    import importlib
    models_path = os.path.join(os.getcwd(), 'core', 'models')
    if os.path.exists(models_path):
        for item in os.listdir(models_path):
            if item.endswith('.py') and not item.startswith('__'):
                importlib.import_module(f"core.models.{item[:-3]}")
    addons_path = os.path.join(os.getcwd(), 'addons')
    if os.path.exists(addons_path):
        sys.path.append(addons_path)
        from core.module_graph import load_modules_topological
        for item in load_modules_topological(addons_path):
            importlib.import_module(f"addons.{item}")

async def debug_login():
    print("DEBUG LOGIN: Initializing DB...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
         from core.env import Environment
         from core.registry import Registry
         
         sudo_env = Environment(cr, uid=1)
         Users = sudo_env['res.users']
         
         login = 'admin'
         password = 'admin'
         
         print(f"DEBUG LOGIN: Checking {login} / {password}...")
         
         # 1. Search User in DB
         users = await Users.search([('login', '=', login)])
         print(f"DEBUG LOGIN: Search Result: {users}")
         
         if not users:
             print("DEBUG LOGIN: FAIL - User not found in search.")
             # Check raw SQL
             await cr.execute("SELECT id, login, password FROM res_users WHERE login = 'admin'")
             raw = cr.fetchall()
             print(f"DEBUG LOGIN: RAW SQL CHECK: {raw}")
             # Check if login column is actually populated or if fix_schema created it as NULL.
             # If created as NULL, the search [('login', '=', 'admin')] fails if value is NULL.
             # reset_admin.py SHOULD have updated it.
         else:
             user = users[0]
             print(f"DEBUG LOGIN: Found User ID {user.id}")
             
             # 2. Check Password Field
             data = await user.read(['password', 'login'])
             print(f"DEBUG LOGIN: User Data: {data}")
             
             stored_hash = data[0]['password']
             print(f"DEBUG LOGIN: Stored Hash: {stored_hash}")
             
             # 3. Verify
             from core.auth import verify_password
             try:
                 valid = verify_password(password, stored_hash)
                 print(f"DEBUG LOGIN: Verify Result: {valid}")
             except Exception as e:
                 print(f"DEBUG LOGIN: Verify Error: {e}")
                 
             # 4. Check Credentials Method
             uid = await Users._check_credentials(login, password)
             print(f"DEBUG LOGIN: _check_credentials returned UID: {uid}")

    await AsyncDatabase.close()

if __name__ == "__main__":
    load_modules()
    asyncio.run(debug_login())
