import sys
import os
from core.db import Database
from core.registry import Registry
from core.env import Environment
import core.models
import addons.base.models

def run_test():
    print("--- Testing UI View Engine ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.setup_models(cr) # Ensure ir_ui_view exists
        
        env = Environment(cr, uid=1)
        
        # 1. Define XML Arch
        xml_arch = """
        <form>
            <group>
                <field name="name"/>
                <field name="email"/>
            </group>
            <notebook>
                <page string="Contacts">
                    <field name="child_ids"/> 
                </page>
            </notebook>
        </form>
        """
        
        # 2. Create View Record
        print("Creating View...")
        IrUiView = env['ir.ui.view']
        view = IrUiView.create({
            'name': 'res.partner.form',
            'model': 'res.partner',
            'type': 'form',
            'arch': xml_arch,
            'priority': 16
        })
        print(f"View Created: ID {view.id}")
        
        # 3. Call get_view_info
        print("Fetching View Info from Model...")
        Partner = env['res.partner']
        res = Partner.get_view_info(view_type='form')
        
        # 4. Verification
        print(f"Model: {res['model']}")
        print(f"Fields Found: {list(res['fields'].keys())}")
        print("Architecture JSON snippet:")
        print(res['arch'])
        
        has_name = 'name' in res['fields']
        root_tag = res['arch']['tag']
        
        if has_name and root_tag == 'form':
            print("SUCCESS: View parsed and fields linked.")
        else:
             print("FAILURE: Parsing error.")

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
