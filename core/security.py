
from typing import Tuple, Optional, Any

class AccessCache:
    """
    Global LRU-like Cache for Access Control Lists (ACLs).
    Stores results of check_access_rights to avoid repetitive DB hits.
    Shared across the process (Global state).
    """
    _cache = {} 
    _lock = None

    @classmethod
    def _get_lock(cls):
        import asyncio
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def get(cls, key: Tuple) -> Optional[bool]:
        # Read can be sync for speed (unlocked read is reasonably safe for dicts)
        # We accept a tiny race where get fails if cleared mid-operation.
        return cls._cache.get(key)
        
    @classmethod
    async def set(cls, key: Tuple, value: bool):
        # Write needs lock for eviction logic concurrency
        lock = cls._get_lock()
        async with lock:
            if len(cls._cache) > 50000:
                cls._cache.clear()
            cls._cache[key] = value
        
    @classmethod
    async def invalidate(cls):
        """
        Clears the entire cache. 
        Should be called when ir.model.access is modified.
        """
        lock = cls._get_lock()
        async with lock:
            cls._cache.clear()
