import sys
from datetime import datetime, timedelta
from core.db import Database
from core.registry import Registry
from core.env import Environment
import core.models
import addons.base.models
from core.orm import TransientModel

# Define a Transient Model for testing
class TestWizard(TransientModel):
    _name = 'test.wizard'
    _description = 'Test Transient'
    from core.fields import Char
    name = Char()

def run_test():
    print("--- Testing Record Rules & Transient ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.setup_models(cr)
        
        # 1. Setup Data
        env_admin = Environment(cr, uid=1)
        Partner = env_admin['res.partner']
        
        p_public = Partner.create({'name': 'Public Partner', 'email': 'pub@test.com'})
        p_private = Partner.create({'name': 'Private Partner', 'email': 'priv@test.com'})
        
        # 2. Create Global Rule: Only see "Public" in name
        m_partner = env_admin['ir.model'].search([('model', '=', 'res.partner')])[0]
        
        env_admin['ir.rule'].create({
            'name': 'Only Public',
            'model_id': m_partner.id,
            'domain_force': "[('name', 'ilike', 'Public')]",
            'perm_read': True
        })
        print("Created Rule: Name must contain 'Public'")
        
        # 3. Test Config: Need to allow access first (ACL) because default is Deny
        env_admin['ir.model.access'].create({
            'name': 'Partner Read All',
            'model_id': m_partner.id,
            'perm_read': 1,
            'perm_write': 0, 'perm_create': 0, 'perm_unlink': 0
        })
        
        # 4. As User (UID 2)
        env_user = Environment(cr, uid=2)
        print("Searching as User (UID 2)...")
        res = env_user['res.partner'].search([])
        names = [r.name for r in res]
        print(f"Results: {names}")
        
        if 'Public Partner' in names and 'Private Partner' not in names:
            print("SUCCESS: Rule enforcement worked.")
        else:
            print("FAILURE: Rules failed.")
            
        # 5. Test Transient Model
        print("\nTesting Transient Model...")
        tm = env_admin['test.wizard'] # Auto registered? No, need to be in Registry.
        # We defined class dynamically here, might need manual register or use ir.ui.view as mock?
        # Standard approach: Models must be defined at import time.
        # Hack: Inject into registry
        Registry.register('test.wizard', TestWizard) # Manually register for test
        TestWizard._fields = {'name': TestWizard.name, 'id': env_admin['ir.model']._fields['id'], 'create_date': env_admin['ir.model']._fields['create_date']} # Hack fields init
        TestWizard._table = 'test_wizard'
        # Auto init table
        TestWizard._auto_init(cr)
        
        w1 = env_admin['test.wizard'].create({'name': 'Temp 1'})
        print(f"Created Wizard ID: {w1.id}")
        
        # Vacuum
        # Mock create_date to old
        old_date = datetime.now() - timedelta(hours=5)
        cr.execute("UPDATE test_wizard SET create_date = %s WHERE id = %s", (old_date, w1.id))
        
        w1._transient_vacuum(age_hours=1)
        
        # Verify deletion
        exists = env_admin['test.wizard'].search([('id', '=', w1.id)])
        if not exists:
            print("SUCCESS: Transient Vacuum worked.")
        else:
            print("FAILURE: Vacuum failed.")

        conn.commit()  # Or rollback to clean up? For persistence testing we commit.
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
