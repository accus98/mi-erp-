
import os
import redis
import json
import logging

class RedisCache:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def initialize(self):
        if self.initialized: return
        
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.db = int(os.getenv('REDIS_DB', 0))
        self.password = os.getenv('REDIS_PASSWORD', None)
        
        self.use_redis = True
        self.memory_store = {}
        
        try:
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True
            )
            self.redis.ping()
            print("Cache: Connected to Redis.")
        except Exception as e:
            print(f"Cache Warning: Redis connection failed ({e}). Using In-Memory Fallback.")
            self.use_redis = False
            
        self.initialized = True

    def get(self, key, default=None):
        if not self.initialized: self.initialize()
        
        # L1: Memory
        if key in self.memory_store:
            return self.memory_store[key]

        # L2: Redis
        try:
            if self.use_redis:
                val = self.redis.get(key)
                if val is not None:
                    try:
                        data = json.loads(val)
                    except:
                        data = val
                    
                    # Populate L1
                    self.memory_store[key] = data
                    return data
        except Exception as e:
            print(f"Cache Error (get): {e}")
            
        return default

    def set(self, key, value, ttl=3600):
        if not self.initialized: self.initialize()
        
        # L1: Memory
        self.memory_store[key] = value
        
        # L2: Redis
        try:
            val_str = json.dumps(value)
            if self.use_redis:
                self.redis.setex(key, ttl, val_str)
        except Exception as e:
            print(f"Cache Error (set): {e}")

    def delete(self, key):
        if not self.initialized: self.initialize()
        
        # L1
        if key in self.memory_store:
            del self.memory_store[key]
            
        # L2
        try:
            if self.use_redis:
                self.redis.delete(key)
        except Exception as e:
             print(f"Cache Error (delete): {e}")

    def invalidate_model(self, model, ids=None):
        """
        Invalidate L1 cache for specific records.
        Called by Bus Listener when other workers modify data.
        """
        if not self.initialized: self.initialize() # Should be initialized by then
        
        # Naive Invalidation: Iterate keys?
        # Keys are (model, id, field).
        # We need efficient invalidation.
        # Store keys by model/id index?
        # Or just iterate memory_store (fast enough for typical cache size).
        
        try:
            keys_to_del = []
            for key in self.memory_store:
                if isinstance(key, tuple) and len(key) >= 2:
                    k_model, k_id = key[0], key[1]
                    if k_model == model:
                        if ids is None or k_id in ids:
                            keys_to_del.append(key)
            
            for k in keys_to_del:
                del self.memory_store[k]
                
            if keys_to_del:
                print(f"Cache: Invalidated {len(keys_to_del)} keys for {model}")
        except Exception as e:
            print(f"Cache Error (invalidate): {e}")

# Global Instance
Cache = RedisCache()
