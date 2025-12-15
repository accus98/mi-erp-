import sys
import os
from core.orm import Model
from core.fields import Char
from core.db import Database
from core.registry import Registry
from core.env import Environment
from core.tools.csv_loader import CsvLoader
import core.models
import addons.base.models

def run_test():
    print("--- Testing Security & Usability ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.setup_models(cr)
        env = Environment(cr, uid=1)

        # 1. Test name_get & default_get
        Partner = env['res.partner']
        
        # Test Default
        # (Assuming we add a default to a field, but we didn't modify res.partner yet. 
        # Let's verify defaults logic exists in create even if empty)
        p = Partner.create({'name': 'Secured Partner'})
        print(f"Created: {p.name_get()}") # Should be [(id, 'Secured Partner')]
        
        assert p.name_get()[0][1] == 'Secured Partner'
        print("SUCCESS: name_get works.")
        
        # 2. Test Security Hooks (Bypass Admin)
        # Should pass
        p.write({'name': 'Modified Partner'})
        print("SUCCESS: Admin Write Access allowed.")
        
        # 3. CSV Loader Test (Mock file)
        # Create a dummy CSV
        with open('test_access.csv', 'w') as f:
            f.write("id,name,model_name,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n")
            f.write("access_test,Test Access,res.partner,group_user,1,1,1,1\n")
            
        loader = CsvLoader(env)
        loader.load_file('test_access.csv')
        
        # Check if record created
        acls = env['ir.model.access'].search([('name', '=', 'Test Access')])
        if acls:
             print("SUCCESS: CSV Access Loaded.")
        else:
             print("FAILURE: CSV Load failed.")
             
        # Cleanup
        if os.path.exists('test_access.csv'):
            os.remove('test_access.csv')

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
