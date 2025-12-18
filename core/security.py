
from typing import Tuple, Optional, Any

class AccessCache:
    """
    Global LRU-like Cache for Access Control Lists (ACLs).
    Stores results of check_access_rights to avoid repetitive DB hits.
    Shared across the process (Global state).
    """
    _cache = {} 
    
    @classmethod
    def get(cls, key: Tuple) -> Optional[bool]:
        return cls._cache.get(key)
        
    @classmethod
    def set(cls, key: Tuple, value: bool):
        # Prevention of unlimited growth
        # Simple mechanism: If too big, clear half or all.
        # Given ACL keys are finite permutations of (groups, model, op), 
        # it shouldn't grow indefinitely unless groups are dynamic.
        if len(cls._cache) > 50000:
            cls._cache.clear()
            
        cls._cache[key] = value
        
    @classmethod
    def invalidate(cls):
        """
        Clears the entire cache. 
        Should be called when ir.model.access is modified.
        """
        cls._cache.clear()
