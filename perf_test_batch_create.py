import asyncio
import time
from core.db_async import AsyncDatabase
from core.registry import Registry
import addons.base.models.res_users

async def run_benchmark():
    db = AsyncDatabase()
    await db.initialize()
    
    async with db.acquire() as conn:
        await Registry.setup_models(conn)
    
    from core.env import Environment
    async with db.acquire() as conn:
        env = Environment(conn, uid=1)
        Users = env['res.users']
        
        # Prepare 1000 records
        vals_list = [{'login': f'batch_user_{i}', 'password': 'pwd'} for i in range(1000)]
        
        print("Benchmarking Batch Create (1000 records)...")
        start = time.time()
        
        # This should trigger ONE INSERT query
        new_users = await Users.create(vals_list)
        
        end = time.time()
        duration = end - start
        
        print(f"Time taken: {duration:.4f}s")
        print(f"Created count: {len(new_users)}")
        
        assert len(new_users) == 1000, f"Expected 1000, got {len(new_users)}"
        
        # Verify IDs are sequential (optional but likely)
        ids = new_users.ids
        print(f"ID Range: {min(ids)} - {max(ids)}")
        
        print("Success! Batch Create Passed.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
