
from core.db import Database
from core.env import Environment
from core.registry import Registry
import addons.base.models.res_users # Register
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def debug_pwd():
    conn = Database.connect()
    cr = conn.cursor()
    Registry.setup_models(cr)
    env = Environment(cr, uid=1)
    
    users = env['res.users'].search([('login', '=', 'admin')])
    print(f"Found {len(users)} admin users.")
    
    for u in users:
        print(f"User ID: {u.id}, Login: {u.login}")
        hash_val = u.password
        print(f"Hash: {hash_val}")
        
        is_valid = pwd_context.verify("admin", hash_val)
        print(f"Verify 'admin' vs Hash: {is_valid}")
        
        if not is_valid:
            print("Trying to reset password manually via hash...")
            new_hash = pwd_context.hash("admin")
            # Bypass ORM write to ensure RAW SQL update if needed, but ORM should work
            # u.write({'password': 'admin'}) # This would double hash if logic is there?
            # My logic in res_users.py: if 'password' in vals: hash it.
            # So u.write({'password': 'admin'}) -> hashed.
            
            # Let's try ORM write again
            u.write({'password': 'admin'})
            print("Password updated via ORM. Re-verifying...")
            # Reload
            u_new = env['res.users'].browse([u.id])[0]
            print(f"New Hash: {u_new.password}")
            print(f"New Verify: {pwd_context.verify('admin', u_new.password)}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    debug_pwd()
