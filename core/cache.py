
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
        
        try:
            if self.use_redis:
                val = self.redis.get(key)
                if val is not None:
                    try:
                        return json.loads(val)
                    except:
                        return val
            else:
                return self.memory_store.get(key, default)
        except Exception as e:
            print(f"Cache Error (get): {e}")
            return default
            
        return default

    def set(self, key, value, ttl=3600):
        if not self.initialized: self.initialize()
        
        try:
            val_str = json.dumps(value)
            if self.use_redis:
                self.redis.setex(key, ttl, val_str)
            else:
                self.memory_store[key] = value
                # Need to implement TTL cleanup for memory store? 
                # For basic session dev usage, strict TTL cleanup in memory isn't critical.
        except Exception as e:
            print(f"Cache Error (set): {e}")

    def delete(self, key):
        if not self.initialized: self.initialize()
        
        try:
            if self.use_redis:
                self.redis.delete(key)
            else:
                if key in self.memory_store:
                    del self.memory_store[key]
        except Exception as e:
             print(f"Cache Error (delete): {e}")

# Global Instance
Cache = RedisCache()
