import sys
from datetime import datetime, timedelta
from core.db import Database
from core.registry import Registry
from core.env import Environment
import core.models
import addons.base.models
from core.models.ir_cron import IrCron
from core.fields import Binary

# define a model with binary
from core.orm import Model
class ModelWithBin(Model):
    _name = 'test.binary'
    from core.fields import Char
    name = Char()
    image = Binary()

def run_test():
    print("--- Testing Living Infrastructure ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.register('test.binary', ModelWithBin)
        Registry.setup_models(cr)
        
        env = Environment(cr, uid=1)
        
        # 1. Test Binary Persistence
        print("\n[1] Binary Field (Attachments)")
        m = env['test.binary'].create({'name': 'T1', 'image': 'DATA_BASE64_MOCK'})
        print(f"Created Record {m.id}")
        
        # Check Attachment existence
        atts = env['ir.attachment'].search([
            ('res_model', '=', 'test.binary'),
            ('res_id', '=', m.id),
            ('name', '=', 'image')
        ])
        print(f"Attachments found: {len(atts)}")
        if atts and atts[0].datas == 'DATA_BASE64_MOCK':
            print("SUCCESS: Persistence working.")
        else:
            print("FAILURE: Attachment missing or content mismatch.")
            
        # Check Read
        m_read = env['test.binary'].browse([m.id])
        print(f"Read Content: {m_read.image}")
        if m_read.image == 'DATA_BASE64_MOCK':
            print("SUCCESS: Read working.")
        
        # 2. Test Cron
        print("\n[2] Cron Execution")
        # Define a cron that runs a method on test.binary
        # We need a method first.
        def dummy_cron_method(self):
            print(">>> CRON TRIGGERED <<<")
            
        ModelWithBin.my_cron_job = dummy_cron_method
        
        cron = env['ir.cron'].create({
            'name': 'Test Job',
            'model_id': env['ir.model'].search([('model', '=', 'test.binary')])[0].id,
            'method': 'my_cron_job',
            'interval_number': 1,
            'interval_type': 'minutes',
            'nextcall': datetime.now() - timedelta(seconds=1) # Ready now
        })
        
        conn.commit()
        conn.close() 
        
        # Run Runner manually
        params = Database._pool_args if hasattr(Database, '_pool_args') else {} # Mock or reuse
        # We need actual connection params used in Database.connect() default?
        # Database.connect() uses env vars.
        # IrCron.process_jobs({}) should use default.
        
        print("Running Job Runner...")
        IrCron.process_jobs({})
        
        # Verification: Check nextcall moved
        conn2 = Database.connect()
        cr2 = Database.cursor(conn2)
        env2 = Environment(cr2, uid=1)
        c2 = env2['ir.cron'].browse([cron.id])
        print(f"Job Next Call: {c2.nextcall}")
        if c2.nextcall > datetime.now():
            print("SUCCESS: Job processed and rescheduled.")
        else:
            print("FAILURE: Job did not run or reschedule.")

        conn2.commit()
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
