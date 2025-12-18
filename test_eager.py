
import asyncio
from core.orm import Model
from core.fields import Char
from core.registry import Registry

# Mock Environment and Database
class MockRow:
    def __init__(self, data):
        self.data = data
    def __getitem__(self, key):
        if key == 0: return self.data['id']
        return self.data[key]

class MockCr:
    async def execute(self, query, params=None):
        pass
    def fetchall(self):
        return [MockRow({'id': 1}), MockRow({'id': 2})]
    def fetchone(self):
        return MockRow({'id': 1})

class MockEnv:
    def __init__(self):
        self.cr = MockCr()
        self.uid = 1
        self.cache = {}
        self.registry = Registry
        self.user = None
        self.company = None
        self.permission_cache = {}
        
    def __getitem__(self, key):
        cls = Registry.get(key)
        return cls(self)
        
    def get(self, key):
        # Used by browse()
        cls = Registry.get(key)
        return cls(self)

class TestModel(Model):
    _name = 'test.eager'
    name = Char()

# Register
Registry.register('test.eager', TestModel)

async def test_eager():
    env = MockEnv()
    model = TestModel(env)
    
    # Mock read manually since we mocked CR
    # We want to verify `record.read` is called.
    # But read calls CR.
    # We can inspect env.cache?
    # If `search` calls `read`, `read` populates cache.
    # But our MockCr returns nothing meaningful for read queries.
    # We need to spy on `read`.
    
    original_read = TestModel.read
    read_called = False
    
    async def mock_read(self, fields=None):
        nonlocal read_called
        read_called = True
        print(f"Read called with: {fields}")
        return []
        
    TestModel.read = mock_read
    
    # Test
    print("Testing search(include=['name'])...")
    await model.search([], include=['name'])
    
    if read_called:
        print("PASS: Read was called.")
    else:
        print("FAIL: Read was NOT called.")
        exit(1)
        
    # Restore
    TestModel.read = original_read

if __name__ == "__main__":
    asyncio.run(test_eager())
