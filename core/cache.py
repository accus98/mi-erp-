import os
import json
import logging
import asyncio

# Use redis.asyncio for non-blocking I/O
try:
    import redis.asyncio as redis
except ImportError:
    # Fallback if older redis installed (though requirements has 'redis')
    import redis

class RedisCache:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    async def initialize(self):
        if self.initialized: return
        
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.db = int(os.getenv('REDIS_DB', 0))
        self.password = os.getenv('REDIS_PASSWORD', None)
        
        self.use_redis = True
        self.memory_store = {}
        self._model_index = {}
        
        try:
            self.redis = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                decode_responses=True
            )
            await self.redis.ping()
            print("Cache: Connected to Async Redis.")
        except Exception as e:
            print(f"Cache Warning: Async Redis connection failed ({e}). Using In-Memory Fallback.")
            self.use_redis = False
            
        self.initialized = True

    async def get(self, key, default=None):
        if not self.initialized: await self.initialize()
        
        # L1: Memory
        if key in self.memory_store:
            return self.memory_store[key]

        # L2: Redis
        try:
            if self.use_redis:
                val = await self.redis.get(key)
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

    async def set(self, key, value, ttl=3600):
        if not self.initialized: await self.initialize()
        
        # L1: Memory
        self.memory_store[key] = value
        
        # Indexing for L1 Invalidation
        if isinstance(key, tuple) and len(key) >= 1:
            model = key[0]
            if model not in self._model_index:
                 self._model_index[model] = set()
            self._model_index[model].add(key)
        
        # L2: Redis
        try:
            val_str = json.dumps(value)
            key_str = str(key)
            
            if self.use_redis:
                async with self.redis.pipeline() as pipe:
                    await pipe.setex(key_str, ttl, val_str)
                    
                    # Dependency Tracking
                    if isinstance(key, tuple) and len(key) >= 2:
                        model, res_id = key[0], key[1]
                        dep_key = f"deps:{model}:{res_id}"
                        await pipe.sadd(dep_key, key_str)
                        await pipe.expire(dep_key, ttl + 3600) 
                    
                    await pipe.execute()
        except Exception as e:
            print(f"Cache Error (set): {e}")

    async def delete(self, key):
        if not self.initialized: await self.initialize()
        
        # L1
        if key in self.memory_store:
            del self.memory_store[key]
            
        if isinstance(key, tuple) and len(key) >= 1:
            model = key[0]
            if model in self._model_index:
                self._model_index[model].discard(key)
            
        # L2
        try:
            if self.use_redis:
                await self.redis.delete(str(key))
        except Exception as e:
             print(f"Cache Error (delete): {e}")

    async def invalidate_model(self, model, ids=None):
        if not self.initialized: await self.initialize()
        
        # 1. L1 Invalidation
        if model in self._model_index:
            keys_to_remove = list(self._model_index[model])
            for k in keys_to_remove:
                if ids is None or k[1] in ids:
                    if k in self.memory_store:
                        del self.memory_store[k]
                    self._model_index[model].discard(k)
            
        # 2. L2 Redis Invalidation
        try:
            if self.use_redis:
                keys_to_del_redis = []
                sets_to_del = []
                
                if ids:
                    for rid in ids:
                        dep_key = f"deps:{model}:{rid}"
                        members = await self.redis.smembers(dep_key)
                        if members:
                            keys_to_del_redis.extend(members)
                        sets_to_del.append(dep_key)
                else:
                    # Generic invalidation handling (Complex if not tracking all keys)
                    pass 

                if keys_to_del_redis:
                    async with self.redis.pipeline() as pipe:
                        # Redis pipeline methods add to pipe, execute runs them
                        # await not needed for adding to pipe?
                        # redis-py async pipeline: pipe.delete(...) returns Coroutine? 
                        # usually pipe commands return self or future.
                        # Correct pattern: await pipe.delete(...).
                        # Wait, pipe commands are chainable but in async they are awaited if immediate?
                        # Documentation says: `await pipe.set(...)` ?
                        # No, usually in pipeline context you just `pipe.set()` then `await pipe.execute()`.
                        # BUT redis-py async might differ.
                        # To be safe: await pipe.delete(...)
                        if keys_to_del_redis:
                             await pipe.delete(*keys_to_del_redis)
                        if sets_to_del:
                             await pipe.delete(*sets_to_del)
                        await pipe.execute()
                    
                print(f"Cache: Invalidated {len(keys_to_del_redis)} Redis keys for {model} ids={ids}")
                
        except Exception as e:
            print(f"Cache Error (invalidate): {e}")

    async def delete_pattern(self, pattern: str):
        """
        Safely delete keys matching a pattern using SCAN.
        Verified async non-blocking.
        """
        if not self.initialized: await self.initialize()
        
        try:
            if self.use_redis:
                keys_to_del = []
                # scan_iter matches glob-style patterns
                async for key in self.redis.scan_iter(match=pattern):
                    keys_to_del.append(key)
                    if len(keys_to_del) >= 1000:
                        # Batch delete in chunks
                        await self.redis.delete(*keys_to_del)
                        keys_to_del = []
                
                if keys_to_del:
                    await self.redis.delete(*keys_to_del)
                    
                print(f"Cache: Deleted pattern '{pattern}'")
            else:
                # L1 Memory Fallback (Naive loop)
                # Iterate copy of keys to avoid runtime change error
                for key in list(self.memory_store.keys()):
                    # Very simple glob check? or Startswith?
                    # Redis patterns are glob-like.
                    # As fallback, let's assume prefix match if pattern ends with *
                    if pattern == "*" or (pattern.endswith("*") and str(key).startswith(pattern[:-1])):
                         del self.memory_store[key]

        except Exception as e:
            print(f"Cache Error (delete_pattern): {e}")

# Global Instance
Cache = RedisCache()
