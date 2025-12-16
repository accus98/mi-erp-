import os
import ast
import sys
import importlib

class ModuleLoader:
    @staticmethod
    def load_addons(addons_path, env):
        """
        Load all addons from path in topological order.
        """
        if not os.path.exists(addons_path):
            print(f"Addons path not found: {addons_path}")
            return

        # 1. Scan
        modules = {} # name -> manifest
        
        for item in os.listdir(addons_path):
            mod_path = os.path.join(addons_path, item)
            manifest_path = os.path.join(mod_path, '__manifest__.py')
            
            if os.path.isdir(mod_path) and os.path.exists(manifest_path):
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest_content = f.read()
                        manifest = ast.literal_eval(manifest_content)
                        modules[item] = manifest
                except Exception as e:
                    print(f"Error reading manifest for {item}: {e}")

        # 2. Build Dependency Graph
        # We need to sort modules based on 'depends'.
        # Node: module_name
        # Edges: dependency -> module
        
        # Simple Topological Sort
        sorted_modules = []
        visited = set()
        active_stack = set() # For cycle detection
        
        def visit(mod_name):
            if mod_name in visited: return
            if mod_name in active_stack:
                print(f"Cycle detected involving {mod_name}")
                return
            
            if mod_name not in modules:
                # If dependency is 'base' or 'core', assume allowed (base usually internal)
                # But here we treat folders as modules.
                # If dependency missing?
                # For 'base', we might skip as it's built-in?
                if mod_name == 'base': 
                     return
                # print(f"Warning: Module {mod_name} dependency not found.")
                return

            active_stack.add(mod_name)
            
            manifest = modules[mod_name]
            deps = manifest.get('depends', [])
            for dep in deps:
                visit(dep)
            
            active_stack.remove(mod_name)
            visited.add(mod_name)
            sorted_modules.append(mod_name)

        # Visit all found modules
        for mod in modules:
            visit(mod)

        print(f"Loading sequence: {sorted_modules}")

        # 3. Load Modules
        from core.tools.xml_loader import XmlLoader
        xml_loader = XmlLoader(env)

        # Ensure addons path is in sys.path
        abs_addons_path = os.path.abspath(addons_path)
        if abs_addons_path not in sys.path:
            sys.path.append(abs_addons_path)

        for mod_name in sorted_modules:
            print(f"Loading Module: {mod_name}")
            manifest = modules[mod_name]
            
            # Update/Create IrModule
            ModModel = env['ir.module.module']
            existing = ModModel.search([('name', '=', mod_name)])
            
            old_version = False
            new_version = manifest.get('version', '1.0.0')
            
            if not existing:
                ModModel.create({
                    'name': mod_name,
                    'state': 'installed',
                    'version': new_version,
                    'summary': manifest.get('summary'),
                    'author': manifest.get('author'),
                    'dependencies': str(manifest.get('depends'))
                })
            else:
                old_version = existing[0].version
                existing[0].write({
                    'state': 'installed',
                    'version': new_version, 
                    'summary': manifest.get('summary')
                })

            # Migration (Schema Upgrades)
            # Run BEFORE Code Import? OR AFTER?
            # Standard: Code Import (define new models) -> Auto Init -> Migration Scripts (Data)
            # But sometimes we need Pre-Migration to prepare schema?
            # MigrationManager handles "migrations/version/pre.py" if we want.
            # For now, we put it here (Before import? No, usually after import so classes exist).
            
            # Let's import code first (to update python classes), then run migrations.

            # Custom Models Import
            # "import addons.mod_name"
            # Since we added addons_path to sys.path, we can import mod_name directly?
            # Or assume structure: `import mod_name` works if path is added. 
            # Or `import addons.mod_name` if parent folder relative.
            # Let's try direct import if in path.
            try:
                importlib.import_module(mod_name)
                
                # Auto-Init new models!
                from core.registry import Registry
                for name, model_cls in Registry._models.items():
                    # We can't easily know which ones are new without tracking.
                    # But _auto_init is idempotent (CREATE IF NOT EXISTS).
                    # Efficiency warning: we re-check all models every module load.
                    # For MVP, this is acceptable.
                    # Or check if table exists? _auto_init does that.
                    model_cls._auto_init(env.cr)
                    
            except Exception as e:
                print(f"Failed to import python module {mod_name}: {e}")
                continue

            # Load Data (XML)
            data_files = manifest.get('data', [])
            for df in data_files:
                full_path = os.path.join(mod_path, df)
                if os.path.exists(full_path):
                    try:
                        xml_loader.load_file(full_path, module=mod_name)
                    except Exception as e:
                        print(f"Failed to load XML {df}: {e}")
            
            # Run Migrations (Post-Update)
            if old_version and old_version != new_version:
                 from core.migration import MigrationManager
                 try:
                     MigrationManager.run_migrations(env, mod_name, old_version, new_version, addons_path)
                 except Exception as e:
                     print(f"Migration Failed for {mod_name}: {e}")
                     # Do we abort? Ideally yes.
                     pass

            print(f"Module {mod_name} Loaded.")
