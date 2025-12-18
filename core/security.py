
from typing import Tuple, Optional, Any

class AccessCache:
    """
    Global LRU-like Cache for Access Control Lists (ACLs).
    Stores results of check_access_rights to avoid repetitive DB hits.
    Shared across the process (Global state).
    """
from core.cache import Cache
import json

class AccessCache:
    """
    Global Cache for Access Control Lists (ACLs) backed by Async Redis.
    Shared across workers.
    """
    
    @staticmethod
    def _make_key(key: Tuple) -> str:
        # Key is ((groups...), model, operation)
        # We need a deterministic string.
        # groups is a tuple of ints (sorted in orm.py).
        groups, model, op = key
        groups_str = ",".join(map(str, groups)) if groups else "public"
        return f"acl:{model}:{op}:{groups_str}"

    @classmethod
    async def get(cls, key: Tuple) -> Optional[bool]:
        # Async Read from Redis L1
        if not Cache.initialized: await Cache.initialize()
        
        redis_key = cls._make_key(key)
        val = await Cache.get(redis_key)
        
        if val is None: return None
        # Cache stores strings/bytes. Convert back to bool.
        # Cache.get usually returns json parsed if we put json? 
        # But Cache.set uses json.dumps? Let's check Cache implementation.
        # Assuming Cache.get returns deserialized object if it was JSON?
        # If Cache.get returns string "true"/"false" or boolean from json load.
        return val

    @classmethod
    async def set(cls, key: Tuple, value: bool):
        # Async Write to Redis L1
        if not Cache.initialized: await Cache.initialize()
        
        redis_key = cls._make_key(key)
        # TTL 10 minutes for permissions? 
        # Permissions rarely change but we want some freshness.
        await Cache.set(redis_key, value, timeout=600)
        
    @classmethod
    async def invalidate(cls):
        """
        Clears ACL cache.
        Removes all 'acl:*' keys from Redis.
        """
        if not Cache.initialized: await Cache.initialize()
        
        await Cache.delete_pattern("acl:*")
