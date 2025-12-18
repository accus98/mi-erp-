
import asyncio
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.auth import get_password_hash
import os
import sys

# Load Modules Stub (Simplified)
def load_modules():
    import importlib
    # Core
    import core.controllers.main
    models_path = os.path.join(os.getcwd(), 'core', 'models')
    if os.path.exists(models_path):
        for item in os.listdir(models_path):
            if item.endswith('.py') and not item.startswith('__'):
                importlib.import_module(f"core.models.{item[:-3]}")
    # Addons
    addons_path = os.path.join(os.getcwd(), 'addons')
    if os.path.exists(addons_path):
        sys.path.append(addons_path)
        from core.module_graph import load_modules_topological
        for item in load_modules_topological(addons_path):
            importlib.import_module(f"addons.{item}")

async def reset_admin():
    print("Initializing Database...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
         from core.env import Environment
         env = Environment(cr, uid=1)
         
         # 1. Ensure Company
         company_data = {'name': 'Nexo Enterprise'}
         companies = await env['res.company'].search([('name', '=', 'Nexo Enterprise')])
         if not companies:
             print("Creating Company...")
             company = await env['res.company'].create(company_data)
         else:
             company = companies[0]
             
         print("Company ID: {company.id}")

         # 2. Ensure Groups (Seed)
         print("Seeding Groups...")
         ResGroups = env['res.groups']
         
         # System Admin Group
         admins = await ResGroups.search([('name', '=', 'Administration')])
         if not admins:
             admin_group = await ResGroups.create({'name': 'Administration'})
         else:
             admin_group = admins[0]

         # Internal User Group
         users = await ResGroups.search([('name', '=', 'Internal User')])
         if not users:
             user_group = await ResGroups.create({'name': 'Internal User'})
         else:
             user_group = users[0]
             
         # 3. Ensure Access Rights (Bootstrap)
         # Grant Admin full access to core models
         print("Seeding Access Rights...")
         IrModelAccess = env['ir.model.access']
         # Check if rule exists
         rule_domain = [('name', '=', 'Admin Full Access'), ('group_id', '=', admin_group.id)]
         rules = await IrModelAccess.search(rule_domain)
         
         # We need to target specific models or Use Wildcard if supported?
         # Standard Odoo requires 1 rule per model.
         # For Login Fix, we need access to: res.users, res.company, res.partner.
         
         models_to_fix = ['res.users', 'res.company', 'res.partner', 'res.groups']
         processed_models = set()
         
         if rules:
             # Just in case, ensure coverage? No, standard logic.
             pass
         
         # Manual SQL Insert for robustness if ORM is locked
         # But we are Superuser (uid=1) so we can create rules.
         
         for m_name in models_to_fix:
             m_recs = await env['ir.model'].search([('model', '=', m_name)])
             if not m_recs: continue
             m_id = m_recs[0].id
             
             # Create Rule
             has_rule = await IrModelAccess.search([('model_id', '=', m_id), ('group_id', '=', admin_group.id)])
             if not has_rule:
                 await IrModelAccess.create({
                     'name': f'Admin Full {m_name}',
                     'model_id': m_id,
                     'group_id': admin_group.id,
                     'perm_read': True,
                     'perm_write': True,
                     'perm_create': True,
                     'perm_unlink': True
                 })

         # 4. Reset Admin User
         print("Updating Admin User...")
         users = await env['res.users'].search([('login', '=', 'admin')])
         
         # Pass Plaintext - Model handles hashing!
         password_plain = 'admin'
         
         vals = {
             'name': 'Administrator',
             'login': 'admin',
             'password': password_plain,
             'company_id': company.id,
             'company_ids': [(6, 0, [company.id])],
             'groups_id': [(4, admin_group.id), (4, user_group.id)] # Assign Groups
         }
         
         if not users:
             print("Creating Admin User...")
             await env['res.users'].create(vals)
             print("Admin Created.")
         else:
             user = users[0]
             await user.write(vals)
             print("Admin Updated.")
             
    await AsyncDatabase.close()

if __name__ == "__main__":
    load_modules()
    asyncio.run(reset_admin())
