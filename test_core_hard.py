import sys
import os
from core.db import Database
from core.registry import Registry
from core.env import Environment
import core.models
import addons.base.models
from core.tools.xml_loader import XmlLoader
from core.tools.domain_parser import DomainParser

def run_test():
    print("--- Testing Indestructible Core ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.setup_models(cr)
        
        # 1. Test Domain Parser
        print("\n[1] Domain Parser")
        dp = DomainParser()
        # ['|', ('a', '=', 1), '&', ('b', '=', 2), ('c', '=', 3)]
        domain = ['|', ('a', '=', 1), ('b', '=', 2)]
        sql, params = dp.parse(domain)
        print(f"Domain: {domain}")
        print(f"SQL: {sql}")
        print(f"Params: {params}")
        if "OR" in sql:
            print("SUCCESS: OR clause detected.")
        else:
            print("FAILURE: Parser failed.")
        
        # 2. Test Idempotency
        print("\n[2] XML Idempotency")
        env = Environment(cr, uid=1)
        loader = XmlLoader(env)
        
        # Load twice
        loader.load_file('addons/base/data.xml', module='base')
        loader.load_file('addons/base/data.xml', module='base')
        
        # Check count of menus (Should be 1 'Customers' menu, not 2)
        menus = env['ir.ui.menu'].search([('name', '=', 'Customers')])
        print(f"Menu Count: {len(menus)}")
        
        if len(menus) == 1:
            print("SUCCESS: Idempotency achieved.")
        else:
            print("FAILURE: Duplicate records found.")
            
        # 3. Test Safety (Security)
        print("\n[3] Security")
        # Ensure we have a rule for res.partner? 
        # By default we added Check, and default is Deny.
        # But we are UID=1 so we pass.
        # Let's switch to UID=2 (User)
        env_user = Environment(cr, uid=2)
        
        # Create a rule first (We are Admin)
        # Allow Read on res.partner
        # Need model id
        m_partner = env['ir.model'].search([('model', '=', 'res.partner')])[0]
        env['ir.model.access'].create({
            'name': 'Partner Read',
            'model_id': m_partner.id,
            'perm_read': 1,
            'perm_write': 0,
            'perm_create': 0,
            'perm_unlink': 0
        })
        print("Created ACL: Read Only")
        
        try:
            # Read should work
            env_user['res.partner'].search([])
            print("User Read: Allowed (Correct)")
        except Exception as e:
            print(f"User Read Failed: {e}")
            
        try:
            # Write should fail
            p = env_user['res.partner'].search([])
            if p:
                p[0].write({'name': 'HACKED'})
                print("FAILURE: User Write check failed (Should have blocked)")
            else:
                print("Skipping write check (no records)")
        except Exception as e:
            print(f"User Write: Blocked (Correct) -> {e}")

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
