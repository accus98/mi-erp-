
import asyncio
import unittest
from core.orm import Model
from core.registry import Registry
from core.security import AccessCache

# Mock CR to count queries
class MockCr:
    def __init__(self):
        self.query_count = 0
        self.last_query = ""
    
    async def execute(self, query, params=None):
        self.query_count += 1
        self.last_query = query
        
    def fetchone(self):
        return (1,) # Always grant access for test

    def fetchall(self):
        return []

# Mock Env
class MockEnv:
    def __init__(self):
        self.cr = MockCr()
        self.uid = 2 # Not admin
        self.cache = {}
        self.permission_cache = {}
        self.user = None
        
    def __getitem__(self, key):
        if key == 'res.users':
             return MockUser(self)
        return Registry.get(key)(self)

class MockUser(Model):
    _name = 'res.users'
    async def get_group_ids(self):
        return [1, 2] # Dummy groups

class TestModel(Model):
    _name = 'test.acl.cache'

Registry.register('test.acl.cache', TestModel)
Registry.register('res.users', MockUser)

async def test_acl_cache():
    print("Initializing...")
    env = MockEnv()
    model = TestModel(env)
    
    # Reset Cache
    AccessCache.invalidate()
    
    # 1. First Call - Should hit DB
    print("1. Checking Access (First Run)...")
    await model.check_access_rights('read')
    
    if env.cr.query_count == 1:
        print("PASS: DB Query executed on cache miss.")
    else:
        print(f"FAIL: Expected 1 query, got {env.cr.query_count}")
        exit(1)
        
    # 2. Second Call - Should hit Cache (Global)
    # Clear LOCAL env cache to force global check
    env.permission_cache = {}
    
    print("2. Checking Access (Second Run - Cache)...")
    await model.check_access_rights('read')
    
    if env.cr.query_count == 1:
        print("PASS: DB Query NOT executed (Cache Hit).")
    else:
        print(f"FAIL: Expected 1 query (cached), got {env.cr.query_count}. Cache Miss?")
        exit(1)
        
    # 3. Invalidate and Retry
    print("3. Invalidating Cache...")
    AccessCache.invalidate()
    env.permission_cache = {} # Clear local again
    
    await model.check_access_rights('read')
    
    if env.cr.query_count == 2:
        print("PASS: DB Query executed after invalidation.")
    else:
        print(f"FAIL: Expected 2 queries, got {env.cr.query_count}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(test_acl_cache())
