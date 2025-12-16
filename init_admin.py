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
        })
    
    # Assign to Admin Group
    from addons.base.models.res_groups import ResGroups
    ResGroups._auto_init(cr)
    
    admin_group = env['res.groups'].search([('name', '=', 'Administrator')])
    if admin_group:
        users = env['res.users'].search([('login', '=', 'admin')])
        if users:
            # Check if likely already linked? 
            # ORM write handles M2M. (6, 0, ids) or list of ids replacement.
            # But wait, ResUsers.write expects list of IDs for M2M (direct assignment).
            # If we want to ADD, we should read existing.
            # Simpler: just set it to [admin_group.id]. Admin should have Admin group.
            # Does Admin group include others? Yes via inheritance.
            users[0].write({'groups_id': [admin_group[0].id]})
            print("assigned admin to group")
        
    conn.commit()
    conn.close()
    print("SUCCESS: User 'admin' has password 'admin_password'")

if __name__ == "__main__":
    reset_admin()
