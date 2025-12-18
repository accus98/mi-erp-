
import asyncio
from core.orm import Model
from core.fields import Integer
from core.registry import Registry
from core.tools.sql import SQLParams

# Mock Logic
class MockCr:
    def __init__(self):
        self.last_query = ""
        self.last_params = []
        
    async def execute(self, query, params=None):
        self.last_query = query
        self.last_params = params
        print(f"EXECUTE: {query} with {params}")
        
    def fetchall(self):
        return [] # Return empty, we just spy on query

class MockEnv:
    def __init__(self):
        self.cr = MockCr()
        self.uid = 1
        self.cache = {}
        self.permission_cache = {}
        
    def __getitem__(self, key):
        return Registry.get(key)(self)
    
    def get(self, key):
        return Registry.get(key)(self)

class TestCursorModel(Model):
    _name = 'test.cursor'

Registry.register('test.cursor', TestCursorModel)

async def test_cursor():
    env = MockEnv()
    model = TestCursorModel(env)
    
    # Test Cursor
    print("Testing cursor=100...")
    await model.search([], cursor=100)
    
    query = env.cr.last_query
    params = env.cr.last_params
    
    # Verify
    # Query should contain "id" > $n
    # And params should contain 100
    
    if '"id" > $1' in query or '"id" > $2' in query:
        print("PASS: Query contains cursor condition.")
    else:
        print(f"FAIL: Query missing cursor logic: {query}")
        exit(1)
        
    if 100 in params:
        print("PASS: Params contains cursor value.")
    else:
        print(f"FAIL: Params missing cursor value: {params}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(test_cursor())
