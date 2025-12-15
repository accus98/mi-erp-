import sys
import os
from core.db import Database
from core.registry import Registry
from core.env import Environment
from core.tools.xml_loader import XmlLoader
import core.models # Init models

def run_test():
    print("--- Testing XML Loader & Navigation ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        # 1. Sync Models (Ensure tables exist)
        Registry.setup_models(cr)
        
        env = Environment(cr, uid=1)
        loader = XmlLoader(env)
        
        # 2. Load File
        file_path = 'addons/base/data.xml'
        loader.load_file(file_path, module='base')
        
        # 3. Verify Data creation
        # Action
        actions = env['ir.actions.act_window'].search([('name', '=', 'Customers')])
        if actions:
             print(f"SUCCESS: Action 'Customers' created (ID: {actions[0].id})")
        else:
             print("FAILURE: Action missing.")
             
        # Menu with Parent and Action
        menus = env['ir.ui.menu'].search([('name', '=', 'Customers')])
        if menus:
             m = menus[0]
             print(f"SUCCESS: Menu 'Customers' created (ID: {m.id})")
             # Check relations
             if m.parent_id and m.parent_id.name == 'Sales':
                 print(f" - Parent Correct: {m.parent_id.name}")
             else:
                 print(" - FAILURE: Parent link broken.")
                 
             if m.action_id and m.action_id.name == 'Customers':
                 print(f" - Action Correct: {m.action_id.name}")
             else:
                 print(" - FAILURE: Action link broken.")
        else:
             print("FAILURE: Menu missing.")

        # 4. Test Load Menus JSON
        print("Testing Menu JSON generation...")
        tree = env['ir.ui.menu'].load_menus()
        import json
        print(json.dumps(tree, indent=2))
        
        has_root = False
        for node in tree:
            if node['name'] == 'Sales' and node['children']:
                 if node['children'][0]['name'] == 'Customers':
                     has_root = True
        
        if has_root:
            print("SUCCESS: Menu Tree JSON structure is correct.")
        else:
            print("FAILURE: Tree structure invalid.")

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
