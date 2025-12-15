import sys
import os
import shutil
from core.db import Database
from core.registry import Registry
from core.env import Environment
import core.models
from core.modules.module_loader import ModuleLoader

def run_test():
    print("--- Testing Module System & Reports ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.setup_models(cr) # Core
        
        env = Environment(cr, uid=1)
        
        # 1. Setup Mock Addons
        print("\n[1] Mocking Addons...")
        base_dir = os.getcwd()
        test_addons = os.path.join(base_dir, 'test_addons')
        
        if os.path.exists(test_addons):
            shutil.rmtree(test_addons)
        os.makedirs(test_addons)
        
        # Module A
        mod_a = os.path.join(test_addons, 'mod_a')
        os.makedirs(mod_a)
        with open(os.path.join(mod_a, '__init__.py'), 'w') as f: f.write("print('Imported Mod A')\n")
        with open(os.path.join(mod_a, '__manifest__.py'), 'w') as f: 
            f.write("{'name': 'Module A', 'depends': [], 'version': '1.0'}")
            
        # Module B (Depends on A)
        mod_b = os.path.join(test_addons, 'mod_b')
        os.makedirs(mod_b)
        with open(os.path.join(mod_b, '__init__.py'), 'w') as f: f.write("print('Imported Mod B')\n")
        with open(os.path.join(mod_b, '__manifest__.py'), 'w') as f: 
            f.write("{'name': 'Module B', 'depends': ['mod_a'], 'version': '1.0'}")
            
        # 2. Test Loader
        print("\n[2] Running Module Loader...")
        ModuleLoader.load_addons(test_addons, env)
        
        # Verify IrModule
        mods = env['ir.module.module'].search([('name', 'in', ['mod_a', 'mod_b'])])
        names = [m.name for m in mods]
        print(f"Installed Modules: {names}")
        
        if 'mod_a' in names and 'mod_b' in names:
            print("SUCCESS: Modules registered.")
        else:
            print("FAILURE: Modules missing.")
            
        # 3. Test Reporting
        print("\n[3] Testing Report Engine...")
        # Dictionary based report
        report = env['ir.actions.report'].create({
            'name': 'Test Report',
            'model': 'ir.module.module',
            'template': "<h1>Report for {{ docs|length }} modules</h1><ul>{% for m in docs %}<li>{{ m.name }}</li>{% endfor %}</ul>"
        })
        
        html = report.render(docids=[m.id for m in mods])
        print(f"Rendered HTML: {html}")
        
        if "<li>mod_a</li>" in html:
            print("SUCCESS: Jinja2 Rendered correctly.")
        else:
            print("FAILURE: Render output unexpected.")

        # Cleanup
        # shutil.rmtree(test_addons) 
        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
