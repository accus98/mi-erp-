import sys
import os
from core.db import Database
from core.registry import Registry
from core.env import Environment
import core.models
import addons.base.models

def run_test():
    print("--- Testing View Inheritance ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.setup_models(cr)
        env = Environment(cr, uid=1)
        
        # 1. Create Base View
        print("Creating Base View...")
        IrUiView = env['ir.ui.view']
        base_arch = """
        <form>
            <group>
                <field name="name"/>
                <field name="email"/>
            </group>
        </form>
        """
        base_view = IrUiView.create({
            'name': 'test.partner.base',
            'model': 'res.partner',
            'type': 'form',
            'arch': base_arch,
            'priority': 10,
            'mode': 'primary'
        })
        print(f"Base View: {base_view.id}")
        
        # 2. Create Extension View
        # Add 'phone' after names
        print("Creating Extension View...")
        ext_arch = """
        <data>
            <field name="name" position="after">
                <field name="website"/>
            </field>
        </data>
        """
        ext_view = IrUiView.create({
            'name': 'test.partner.ext',
            'model': 'res.partner',
            'type': 'form',
            'arch': ext_arch,
            'priority': 20,
            'inherit_id': base_view.id,
            'mode': 'extension'
        })
        print(f"Extension View: {ext_view.id}")
        
        # 3. Fetch View Info
        print("Fetching Merged View...")
        Partner = env['res.partner']
        # We need to target the Base View ID specifically to test this flow properly?
        # get_view_info(view_id=...)
        info = Partner.get_view_info(view_id=base_view.id)
        
        # 4. Verification
        fields = info['fields']
        print(f"Fields in View: {list(fields.keys())}")
        
        if 'website' in fields:
            print("SUCCESS: Extension applied (Website field found).")
        else:
            print("FAILURE: Website field missing.")
            print(info['arch']) # Debug
            
        # Verify structure?
        # Check if website is after name?
        # We'd need to traverse json. 
        # For MVP 'found' is good enough proof of merging.

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
