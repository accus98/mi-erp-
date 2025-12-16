import os
import importlib.util
from core.logger import logger

class MigrationManager:
    """
    Handles module upgrades and running migration scripts.
    Structure: addons/[module]/migrations/[version]/[pre|post]_migrate.py
    """
    
    @staticmethod
    def run_migrations(env, module_name, old_version, new_version, addons_path):
        """
        Run migration scripts between old_version and new_version.
        Simple approach: Run everything > old_version and <= new_version?
        Or just run a generic 'upgrade.py' if complex logic?
        
        Odoo style: 
        migrations/
            1.1.0/
                pre-migrate.py
                post-migrate.py
            1.2.0/
                ...
        """
        if not old_version:
            # First install
            return

        logger.info(f"Migration: {module_name} {old_version} -> {new_version} checking...")
        
        # Locate migrations folder
        mod_path = os.path.join(addons_path, module_name)
        mig_path = os.path.join(mod_path, 'migrations')
        
        if not os.path.exists(mig_path):
            return

        # Find version folders
        versions = []
        for v_folder in os.listdir(mig_path):
            if os.path.isdir(os.path.join(mig_path, v_folder)):
                versions.append(v_folder)
        
        # Sort versions using packaging.version or simple semantic sort
        # Assuming semantic X.Y.Z
        try:
            versions.sort(key=lambda s: list(map(int, s.split('.'))))
        except:
            versions.sort() # lexicographical fallback
            
        for v in versions:
            if MigrationManager._compare_versions(v, old_version) > 0 and \
               MigrationManager._compare_versions(v, new_version) <= 0:
                   
                   logger.info(f"Migration: Running scripts for {module_name} : {v}")
                   
                   # Run pre/post scripts
                   target_dir = os.path.join(mig_path, v)
                   
                   # Support python scripts
                   for script in sorted(os.listdir(target_dir)):
                       if script.endswith('.py'):
                           script_path = os.path.join(target_dir, script)
                           logger.info(f"Migration: Executing {script}...")
                           try:
                               MigrationManager._exec_script(script_path, env)
                           except Exception as e:
                               logger.error(f"Migration Failed in {script}: {e}")
                               raise e

    @staticmethod
    def _compare_versions(v1, v2):
        """
        Compare two version strings. 
        Returns 1 if v1 > v2, -1 if v1 < v2, 0 if equal.
        """
        def normalize(v):
            return [int(x) for x in v.split(".")]
            
        p1 = normalize(v1)
        p2 = normalize(v2)
        
        if p1 > p2: return 1
        if p1 < p2: return -1
        return 0

    @staticmethod
    def _exec_script(path, env):
        """
        Execute a python script passing 'env' and 'cr' as globals.
        """
        spec = importlib.util.spec_from_file_location("migration_script", path)
        module = importlib.util.module_from_spec(spec)
        
        # Inject context
        module.env = env
        module.cr = env.cr
        
        spec.loader.exec_module(module)
        
        # Check if there is a 'migrate' function
        if hasattr(module, 'migrate'):
             module.migrate(env.cr, env.installed_version) 
