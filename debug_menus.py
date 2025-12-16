from core.modules.module_loader import ModuleLoader
# Mock request or ensure DB connection
import core.db
core.db.Overview = 'erp' # Ensure correct DB

ModuleLoader.load_addons(['base', 'sales', 'web'])
from core.env import Environment

env = Environment(uid=1)
menus = env['ir.ui.menu'].load_menus()
print(f"Total Root Menus: {len(menus)}")
import json
print(json.dumps(menus, indent=2))
