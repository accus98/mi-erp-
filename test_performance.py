import sys
import time
import os
sys.path.append(os.getcwd())

from core.db import Database
from core.registry import Registry
from core.env import Environment
from core.orm import Model
from core.fields import Char, Integer, Many2many

# Setup Models
class TestPerf(Model):
    _name = 'test.perf'
    name = Char(string="Name")
    value = Integer(string="Value")
    tags = Many2many('test.tag', string="Tags")

class TestTag(Model):
    _name = 'test.tag'
    name = Char(string="Tag Name")

def run_test():
    print("--- Performance Benchmark ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.register('test.perf', TestPerf)
        Registry.register('test.tag', TestTag)
        Registry.setup_models(cr)
        
        # Explicit Init
        TestTag._auto_init(cr)
        TestPerf._auto_init(cr)
        
        env = Environment(cr, uid=1)
        
        # 1. M2M Optimization Test
        print("\n[M2M Delta Optimization]")
        tag1 = env['test.tag'].create({'name': 'T1'}).id
        tag2 = env['test.tag'].create({'name': 'T2'}).id
        tag3 = env['test.tag'].create({'name': 'T3'}).id
        
        rec = env['test.perf'].create({'name': 'R1', 'tags': [tag1, tag2]})
        conn.commit()
        
        # Verify Initial State
        # Raw check
        cr.execute(f"SELECT COUNT(*) FROM test_perf_test_tag_rel WHERE test_perf_id = {rec.id}")
        count = cr.fetchone()[0]
        print(f"Initial Tags Count: {count} (Expected 2)")
        
        # Update: Remove T1, Add T3. Keep T2.
        # Old logic: Delete 2, Insert 2. Total 4 ops (or bulk delete + bulk insert).
        # New logic: Delete T1, Insert T3. T2 preserved.
        
        # We can't easily count SQL ops without a proxy/listener, but we verify correctness.
        rec.write({'tags': [tag2, tag3]})
        conn.commit()
        
        cr.execute(f"SELECT test_tag_id FROM test_perf_test_tag_rel WHERE test_perf_id = {rec.id}")
        current_tags = set(r[0] for r in cr.fetchall())
        expected = {tag2, tag3}
        
        if current_tags == expected:
            print("SUCCESS: M2M Update Correctness Verified.")
        else:
            print(f"FAILURE: M2M Update Mismatch. Got {current_tags}, Expected {expected}")

        # 2. N+1 Mapped Optimization
        print("\n[Mapped N+1 Optimization]")
        # Create 100 records
        print("Creating 100 records...")
        for i in range(100):
            env['test.perf'].create({'name': f'Perf {i}', 'value': i})
        conn.commit()
        
        records = env['test.perf'].search([], limit=100)
        
        start_time = time.time()
        names = records.mapped('name')
        end_time = time.time()
        
        print(f"Mapped 100 names in {end_time - start_time:.4f}s")
        if len(names) == 100:
             print("SUCCESS: Mapped retrieved all values.")
        else:
             print(f"FAILURE: Mapped count mismatch: {len(names)}")

        conn.close()
        
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
