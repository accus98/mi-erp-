
import asyncio
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.schema import SchemaManager
import os
import sys

# Load Models Logic
def load_modules():
    print("Loading Modules...")
    import importlib
    
    # Core
    import core.controllers.main
    import core.controllers.binary
    
    models_path = os.path.join(os.getcwd(), 'core', 'models')
    if os.path.exists(models_path):
        for item in os.listdir(models_path):
            if item.endswith('.py') and not item.startswith('__'):
                importlib.import_module(f"core.models.{item[:-3]}")

    # Addons
    addons_path = os.path.join(os.getcwd(), 'addons')
    if os.path.exists(addons_path) and os.path.isdir(addons_path):
        sys.path.append(addons_path)
        from core.module_graph import load_modules_topological
        ordered_addons = load_modules_topological(addons_path)
        for item in ordered_addons:
            importlib.import_module(f"addons.{item}")

async def run_fix():
    print("Initializing Database...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
         manager = SchemaManager(cr)
         print("Running Declarative Migration...")
         await manager.migrate_all()
         
    await AsyncDatabase.close()
    print("Migration Complete.")

if __name__ == "__main__":
    load_modules()
    asyncio.run(run_fix())
