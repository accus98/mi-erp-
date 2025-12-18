
import unittest
import json
from unittest.mock import MagicMock
from core.cache import Cache

class TestL2Cache(unittest.TestCase):
    def setUp(self):
        Cache.initialized = True
        Cache.use_redis = True
        Cache.redis = MagicMock()
        Cache.memory_store = {}
        
    def test_l1_l2_flow(self):
        key = "test_key"
        val = {"foo": "bar"}
        val_json = json.dumps(val)
        
        # 1. SET
        print("Testing SET...")
        Cache.set(key, val)
        
        # Check L1
        self.assertIn(key, Cache.memory_store)
        self.assertEqual(Cache.memory_store[key], val)
        
        # Check L2 (Mock call)
        Cache.redis.setex.assert_called_with(key, 3600, val_json)
        print("PASS: Set writes to L1 and L2.")
        
        # 2. GET (L1 Hit)
        print("Testing GET (L1 Hit)...")
        res = Cache.get(key)
        self.assertEqual(res, val)
        # Should NOT call Redis get if in L1
        Cache.redis.get.assert_not_called()
        print("PASS: Get hits L1.")
        
        # 3. GET (L2 Hit - Simulate L1 Miss)
        print("Testing GET (L2 Hit)...")
        del Cache.memory_store[key] # Clear L1
        
        # Setup Mock Redis to return value
        Cache.redis.get.return_value = val_json
        
        res = Cache.get(key)
        self.assertEqual(res, val)
        Cache.redis.get.assert_called_with(key)
        
        # Check L1 repopulated
        self.assertIn(key, Cache.memory_store)
        print("PASS: Get hits L2 and repopulates L1.")
        
    def test_delete(self):
        key = "del_key"
        Cache.memory_store[key] = "val"
        
        Cache.delete(key)
        
        self.assertNotIn(key, Cache.memory_store)
        Cache.redis.delete.assert_called_with(key)
        print("PASS: Delete clears L1 and L2.")

if __name__ == "__main__":
    unittest.main()
