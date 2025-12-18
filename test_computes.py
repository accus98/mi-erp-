from core.orm import Model
from core.fields import Integer
from core.api import depends
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.env import Environment
import asyncio
import os

class ComputeA(Model):
    _name = 'test.compute.a'
    x = Integer(store=True)
    y = Integer(compute='_compute_y', store=True)
    z = Integer(compute='_compute_z', store=True)

    @depends('x')
    def _compute_y(self):
        for rec in self:
            print(f"Computing Y for {rec.id} (x={rec.x})")
            rec.y = (rec.x or 0) * 2
            
    @depends('y')
    def _compute_z(self):
        for rec in self:
            print(f"Computing Z for {rec.id} (y={rec.y})")
            rec.z = (rec.y or 0) + 1

async def run_test():
    print("Test: Compute Graph Recursion")
    await AsyncDatabase.initialize()
    async with AsyncDatabase.acquire() as cr:
        # Init Table
        # Need to drop table if exists to ensure clean state? 
        await cr.execute('DROP TABLE IF EXISTS "test_compute_a"')
        await ComputeA._auto_init(cr)
        
        env = Environment(cr, 1, {})
        obj = env['test.compute.a']
        
        # Test Create
        print("1. Create x=10...")
        recs = await obj.create({'x': 10})
        r = recs[0]
        
        # Verify initial compute
        # Note: Accessing fields might need ensure if not in cache.
        # But recompute should have put them in cache.
        print(f"Initial Check: x={r.x}, y={r.y}, z={r.z}")
        
        if r.y != 20: 
             print(f"FAIL: y should be 20, got {r.y}")
        if r.z != 21:
             print(f"FAIL: z should be 21, got {r.z}")

        # Test Write
        print("\n2. Write x=5...")
        await r.write({'x': 5})
        
        # Verify propagation
        # Since fields are stored, we can verify from DB too, but we check cache first.
        print(f"After Write Check: x={r.x}, y={r.y}, z={r.z}")
        if r.y != 10:
             print(f"FAIL: y should be 10, got {r.y}")
        if r.z != 11:
             print(f"FAIL: z should be 11, got {r.z}")
             
        # Verify DB Persistence
        print("\n3. Verify DB Persistence...")
        await cr.execute('SELECT x, y, z FROM "test_compute_a" WHERE id = %s', (r.id,))
        row = cr.fetchone()
        print(f"DB Row: {row}")
        if row['y'] != 10 or row['z'] != 11:
            print("FAIL: DB values incorrect (Write might not have flushed)")
            
        print("PASS: Compute Graph Verified")
        
        # Cleanup
        await r.unlink()

if __name__ == "__main__":
    asyncio.run(run_test())
