import asyncio
from core.db_async import AsyncDatabase

async def test_savepoints():
    print("Testing Transaction Savepoints...")
    db = AsyncDatabase()
    await db.initialize()
    
    async with db.acquire() as cr:
        # Cleanup
        await cr.execute("DROP TABLE IF EXISTS test_savepoint")
        await cr.execute("CREATE TABLE test_savepoint (id SERIAL PRIMARY KEY, name TEXT)")
        
        # Outer Transaction
        await cr.execute("INSERT INTO test_savepoint (name) VALUES ('outer')")
        
        try:
            async with cr.savepoint():
                # Inner Transaction (Savepoint)
                await cr.execute("INSERT INTO test_savepoint (name) VALUES ('inner')")
                raise ValueError("Simulated Error")
        except ValueError:
            print("Caught expected error in savepoint.")
            
        # Check result
        await cr.execute("SELECT name FROM test_savepoint")
        rows = cr.fetchall()
        names = [r['name'] for r in rows]
        
        print(f"Rows: {names}")
        
        if 'outer' in names and 'inner' not in names:
            print("SUCCESS: Savepoint rolled back correctly.")
        else:
            print("FAILURE: Savepoint logic incorrect.")
            exit(1)

        # Cleanup
        await cr.execute("DROP TABLE test_savepoint")

if __name__ == "__main__":
    asyncio.run(test_savepoints())
