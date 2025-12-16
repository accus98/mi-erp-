
import os
import sys
import uuid
import time
import json

# Ensure root
sys.path.append(os.getcwd())

from core.cache import Cache
from core.http_fastapi import Session

def test_cache():
    print("--- Testing Core Cache ---")
    Cache.initialize()
    if Cache.use_redis:
        print("Mode: Redis")
    else:
        print("Mode: Memory (Fallback)")
        
    # Set
    Cache.set("test_key", {"foo": "bar"})
    print("Set 'test_key' = {'foo': 'bar'}")
    
    # Get
    val = Cache.get("test_key")
    print(f"Get 'test_key': {val}")
    
    if val != {"foo": "bar"}:
        print("FAIL: Cache Get mismatch")
        return
        
    # Delete
    Cache.delete("test_key")
    val_deleted = Cache.get("test_key")
    print(f"Get deleted: {val_deleted}")
    
    if val_deleted is not None:
        print("FAIL: Cache Delete failed")
        return
        
    print("PASS: Core Cache Operations")

def test_session():
    print("\n--- Testing Session Manager ---")
    
    # New Session
    s = Session.new()
    print(f"Created Session: {s.sid}")
    
    s.uid = 100
    s.login = "redis_user"
    s.context = {'lang': 'es_ES'}
    s.save()
    print("Saved Session Data")
    
    # Load Session
    s2 = Session.load(s.sid)
    if not s2:
        print("FAIL: Session Load returned None")
        return
        
    print(f"Loaded Session: UID={s2.uid}, Login={s2.login}, Ctx={s2.context}")
    
    if s2.uid != 100:
        print("FAIL: Session UID mismatch")
        return
        
    print("PASS: Session Persistence")

if __name__ == "__main__":
    test_cache()
    test_session()
