
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
            key_str = str(key)
            
            if self.use_redis:
                pipeline = self.redis.pipeline()
                pipeline.setex(key_str, ttl, val_str)
                
                # Dependency Tracking for ORM Keys
                if isinstance(key, tuple) and len(key) >= 2:
                    model, res_id = key[0], key[1]
                    # deps:res.users:1
                    dep_key = f"deps:{model}:{res_id}"
                    pipeline.sadd(dep_key, key_str)
                    # Set TTL for dependency set too? (Optional, match key TTL or longer)
                    pipeline.expire(dep_key, ttl + 3600) 
                
                pipeline.execute()
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
                self.redis.delete(str(key))
                # Note: We don't remove from deps set here, 
                # strictly speaking we should, but it will expire or be cleaned on invalidate.
        except Exception as e:
             print(f"Cache Error (delete): {e}")

    def invalidate_model(self, model, ids=None):
        """
        Invalidate L1 and L2 cache for specific records using Redis Sets.
        O(1) complexity per record instead of O(N) scan.
        """
        if not self.initialized: self.initialize()
        
        # 1. L1 Invalidation (Iterative for now, assumed small per process)
        keys_to_del_l1 = []
        for key in list(self.memory_store.keys()):
            if isinstance(key, tuple) and len(key) >= 2:
                k_model, k_id = key[0], key[1]
                if k_model == model:
                    if ids is None or k_id in ids:
                        keys_to_del_l1.append(key)
        
        for k in keys_to_del_l1:
            del self.memory_store[k]
            
        # 2. L2 Redis Invalidation (Sets)
        try:
            if self.use_redis:
                target_ids = ids if ids else [] 
                # If ids is None, we might need to invalidate ALL keys for model.
                # Current deps structure deps:model:id tracks by ID.
                # To support 'invalidate_model(model)', we need 'deps:model:ALL'?
                # Or scan 'deps:model:*'. Scan is better than keys scan.
                # For this refactor, we focus on ID-based invalidation optimization.
                
                keys_to_del_redis = []
                sets_to_del = []
                
                if ids:
                    for rid in ids:
                        dep_key = f"deps:{model}:{rid}"
                        # Get all keys dependent on this record
                        members = self.redis.smembers(dep_key)
                        if members:
                            keys_to_del_redis.extend(members)
                        sets_to_del.append(dep_key)
                else:
                    # Fallback: Invalidate everything for model?
                    # This requires scanning deps:model:*
                    # Or relying on L1 clear.
                    pass 

                if keys_to_del_redis:
                    pipeline = self.redis.pipeline()
                    pipeline.delete(*keys_to_del_redis)
                    pipeline.delete(*sets_to_del)
                    pipeline.execute()
                    
                print(f"Cache: Invalidated {len(keys_to_del_redis)} Redis keys for {model} ids={ids}")
                
        except Exception as e:
            print(f"Cache Error (invalidate): {e}")

# Global Instance
Cache = RedisCache()
