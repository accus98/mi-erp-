import sys
from core.db import Database
from core.registry import Registry
from core.env import Environment
from core.orm import Model
from core.fields import Char
import core.models # Load ir.model, ir.model.fields
import addons.base.models # Load res.groups, res.users

def run_test():
    print("--- Testing Field Level Security ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        # 1. Setup Environment
        # Ensure ir.model.fields has groups_ids column (via auto_init of ir.model.fields)
        # We might need to force init of ir.model.fields if not already done properly with new field
        # Registry.setup_models calls _auto_init for all models.
        
        group_name = 'Test Secret Group'
        
        class TestFLS(Model):
            _name = 'test.fls'
            name = Char(string="Public")
            secret = Char(string="Secret", groups=group_name)
            
        Registry.register('test.fls', TestFLS)
        
        # Run Setup FIRST
        Registry.setup_models(cr)
        
        # Grant Model Access (Required for check_access_rights)
        env = Environment(cr, uid=1)
        # Need model ID
        model_id = env['ir.model'].search([('model', '=', 'test.fls')])[0].id
        env['ir.model.access'].create({
            'name': 'Test FLS Access',
            'model_id': model_id,
            'group_id': None, # All users
            'perm_read': True,
            'perm_write': True,
            'perm_create': True,
            'perm_unlink': True
        })
        conn.commit() # Commit to ensure new user sees it (separate cursor/transaction)

        # Create a Group (Now safe)
        group_name = 'Test Secret Group'
        g = env['res.groups'].search([('name', '=', group_name)])
        if not g:
            g = env['res.groups'].create({'name': group_name})
            print(f"Created Group: {g.id}")
        else:
            g = g[0]
            
        # Create a User WITHOUT Group
        user_name = 'Test User FLS'
        u = env['res.users'].search([('login', '=', 'test_fls')])
        if not u:
            u = env['res.users'].create({'name': user_name, 'login': 'test_fls', 'password': '123'})
            print(f"Created User: {u.id}")
        else:
            u = u[0]
            
        # Create Record
        rec = env['test.fls'].create({'name': 'Public Info', 'secret': 'Top Secret'})
        conn.commit()
        
        # 2. Test READ as User
        print("\n[READ TEST]")
        env_user = Environment(cr, uid=u.id)
        rec_user = env_user['test.fls'].browse([rec.id])
        
        # Read all fields
        print("Reading fields...")
        data = rec_user.read()
        print(f"Data: {data}")
        
        if data:
            vals = data[0]
            if 'secret' not in vals:
                print("SUCCESS: 'secret' field is hidden.")
            else:
                 print("FAILURE: 'secret' field is visible!")
        
        # 3. Test WRITE as User
        print("\n[WRITE TEST]")
        try:
            rec_user.write({'secret': 'Hacked'})
            print("FAILURE: Write to 'secret' succeeded!")
        except Exception as e:
            print(f"SUCCESS: Write blocked: {e}")
            
        # 4. Test User WITH Group
        print("\n[GROUP TEST]")
        # Add user to group
        # Direct SQL to avoid model complexity
        cr.execute("INSERT INTO res_groups_res_users_rel (res_groups_id, res_users_id) VALUES (%s, %s)", (g.id, u.id))
        # Invalidate cache?
        if hasattr(env_user, '_user_groups_cache'):
            del env_user._user_groups_cache[u.id]
        
        data = rec_user.read()
        if data and 'secret' in data[0]:
             print("SUCCESS: 'secret' field is visible with group.")
        else:
             print("FAILURE: 'secret' field is still hidden with group!")

        conn.close()
        
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
