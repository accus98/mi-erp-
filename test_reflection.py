import sys
import os
from core.db import Database
from core.registry import Registry
from core.env import Environment
import core.models # Import IR models
import addons.base.models # Import Business Models

def run_test():
    print("--- Testing Reflection Engine ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        # 1. Trigger Sync
        Registry.setup_models(cr)
        
        env = Environment(cr, uid=1)
        
        # 2. Check ir.model
        print("Checking ir.model for 'res.partner'...")
        models = env['ir.model'].search([('model', '=', 'res.partner')])
        if models:
            print(f"FOUND: res.partner (ID: {models[0].id})")
        else:
            print("FAILURE: res.partner not found in ir.model")
            
        # 3. Check ir.model.fields
        print("Checking ir.model.fields for 'name' in 'res.partner'...")
        fields = env['ir.model.fields'].search([
            ('model_id.model', '=', 'res.partner'),
            ('name', '=', 'name')
        ])
        # Note: chained search ('model_id.model') not implemented in basic ORM yet?
        # Our ORM search currently only supports direct fields.
        # We need to search model first.
        
        if models:
            m_id = models[0].id
            fields = env['ir.model.fields'].search([
                ('model_id', '=', m_id),
                ('name', '=', 'name')
            ])
            if fields:
                 f = fields[0]
                 print(f"FOUND: Field 'name' (Type: {f.ttype})")
            else:
                 print("FAILURE: Field 'name' not found.")

        # 4. Check fields_get API
        print("Checking fields_get() API...")
        fg = env['res.partner'].fields_get(['name', 'email'])
        print(f"Result: {fg}")
        if 'name' in fg and fg['name']['type'] == 'char':
             print("SUCCESS: fields_get works.")
        else:
             print("FAILURE: fields_get extraction failed.")

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
