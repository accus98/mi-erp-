import sys
from core.db import Database
from core.registry import Registry
from core.env import Environment
from core.orm import Model
from core.fields import Char, Text, Integer, Selection
# Import core models to ensure Registry has them
import core.models # This registers ir.model, ir.translation, etc.
import addons.base.models # Registers res.partner etc.

class TestModel(Model):
    _name = 'test.translation'
    name = Char(string="Name", translate=True)

def run_test():
    print("--- Testing Translation ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        # Verify Registry
        if 'ir.translation' not in Registry.keys():
            print("ERROR: ir.translation not registered!")
            return

        # Setup Test Model
        if 'test.translation' not in Registry.keys():
            Registry.register('test.translation', TestModel)
        
        print("Running Registry.setup_models(cr)...")
        Registry.setup_models(cr)
        
        # Check Field Definition
        model_cls = Registry.get('test.translation')
        name_field = model_cls._fields.get('name')
        print(f"Field 'name' translate attribute: {getattr(name_field, 'translate', 'MISSING')}")

        # Ensure table exists (auto_init should have covered it, but double check)
        cr.execute("SELECT to_regclass('test_translation')")
        if not cr.fetchone()[0]:
             print("Forcing _auto_init for test.translation...")
             TestModel._auto_init(cr)
        
        # 1. Create with English (default)
        env = Environment(cr, uid=1, context={'lang': 'en_US'})
        record = env['test.translation'].create({'name': 'Apple'})
        conn.commit()
        print(f"Created Record {record.id} with Name: {record.name}")
        
        # 2. Add Spanish Translation
        print("Writing Spanish translation...")
        env_es = Environment(cr, uid=1, context={'lang': 'es_ES'})
        record_es = env_es['test.translation'].browse([record.id])
        
        # Verify Context
        print(f"Context Lang: {env_es.context.get('lang')}")
        
        record_es.write({'name': 'Manzana'})
        conn.commit()
        print(f"Wrote Spanish Translation: Manzana")
        
        # 3. Verify Database Raw State (Debug)
        cr.execute("SELECT name FROM test_translation WHERE id=%s", (record.id,))
        raw_name = cr.fetchone()[0]
        print(f"RAW DB Name (Should be 'Apple'): {raw_name}")
        
        # 4. Read back in English
        record_en = env['test.translation'].browse([record.id]) 
        print(f"[EN] Name: {record_en.name}")
        
        # 5. Read back in Spanish
        print(f"[ES] Name: {record_es.name}")
        
        if record_en.name == 'Apple' and record_es.name == 'Manzana':
             print("SUCCESS: Translation logic works.")
        else:
             print("FAILURE: Translation mismatch.")

        conn.close()
        
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()
        if 'conn' in locals():
            try:
                conn.rollback()
            except:
                pass

if __name__ == "__main__":
    run_test()
