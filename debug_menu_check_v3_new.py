
import sys
import os
sys.path.append(os.getcwd())

from core.db import Database
from core.env import Environment
from core.registry import Registry

# Reuse DB connection logic
conn = Database.connect()
cr = conn.cursor()

import core.models # <--- IMPORTANT: Registers models

# Setup Registry
Registry.setup_models(cr)

uid = 1 # Admin
env = Environment(cr, uid)
Menu = env['ir.ui.menu']

# 1. Count Menus
all_menus = Menu.search([])
print(f"Total Menus (Admin): {len(all_menus)}")

# 2. Check content
for m in all_menus:
    print(f"ID: {m.id} | Name: {m.name} | Parent: {m.parent_id.id} | Action: {m.action_id.id}")

# 3. Simulate load_menus
try:
    tree = Menu.load_menus()
    print(f"Tree Roots: {len(tree)}")
    import json
    print(json.dumps(tree, indent=2))
except Exception as e:
    print(f"Error in load_menus: {e}")
    import traceback
    traceback.print_exc()

conn.close()
