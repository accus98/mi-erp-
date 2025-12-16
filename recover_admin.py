
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.db import Database
from core.registry import Registry
from core.env import Environment
import addons.base.models.res_users

def recover_admin():
    print("Connecting to Database...")
    conn = Database.connect()
    cr = conn.cursor()
    
    print("Setting up Registry...")
    Registry.setup_models(cr)
    
    env = Environment(cr, uid=1)
    
    print("Searching for admin user...")
    users = env['res.users'].search([('login', '=', 'admin')])
    
    if not users:
        print("Admin user not found! Creating one...")
        env['res.users'].create({
            'name': 'Administrator',
            'login': 'admin',
            'password': 'admin' # Model handles hashing
        })
        print("Admin user created with password 'admin'.")
    else:
        u = users[0]
        print(f"Admin user found (ID: {u.id}). Resetting password...")
        u.write({'password': 'admin'})
        print("Password reset to 'admin'.")
        
    conn.commit()
    print("Done.")

if __name__ == "__main__":
    recover_admin()
