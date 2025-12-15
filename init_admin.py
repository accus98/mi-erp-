from core.db import Database
from core.env import Environment
from addons.base.models.res_users import ResUsers

def reset_admin():
    print("Connecting to DB...")
    conn = Database.connect()
    cr = Database.cursor(conn)
    
    # Ensure Table
    from addons.base.models.res_partner import ResPartner
    ResPartner._auto_init(cr)
    ResUsers._auto_init(cr)
    
    # Init Env (using uid=1 superuser context)
    env = Environment(cr, uid=1)
    
    # Search Admin
    users = env['res.users'].search([('login', '=', 'admin')])
    
    if users:
        print("Updating existing admin password...")
        # Write (hashing handled by model)
        users[0].write({'password': 'admin_password'})
    else:
        print("Creating admin user...")
        env['res.users'].create({
            'name': 'Administrator',
            'login': 'admin', 
            'password': 'admin_password'
        })
        
    conn.commit()
    conn.close()
    print("SUCCESS: User 'admin' has password 'admin_password'")

if __name__ == "__main__":
    reset_admin()
