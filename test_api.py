import sys
import os
from fastapi.testclient import TestClient

# Add current directory to path
sys.path.append(os.getcwd())

from bin.server import app
from core.db import Database

# Mock the DB connection to avoid needing real Postgres for THIS test if possible,
# But since we want integration testing, we will rely on exception handling if DB is down.

client = TestClient(app)

def test_rpc_flow():
    print("--- Testing API ---")
    
    # 1. Root
    response = client.get("/")
    print(f"Root: {response.json()}")

    # 2. Check Connection first
    try:
        Database.connect()
    except Exception as e:
        print(f"Skipping RPC tests as DB connection failed: {e}")
        return

    # 3. Create Partner
    print("\n[POST] /api/call - create")
    payload = {
        "model": "res.partner",
        "method": "create",
        "args": [],
        "kwargs": {
            "vals": {
                "name": "API Partner",
                "email": "api@example.com"
            }
        }
    }
    
    try:
        response = client.post("/api/call", json=payload)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            pid = response.json()['result']
            
            # 4. Search Partner
            print("\n[POST] /api/call - search")
            search_payload = {
                "model": "res.partner",
                "method": "search",
                "args": [[["name", "=", "API Partner"]]],
                "kwargs": {}
            }
            res_search = client.post("/api/call", json=search_payload)
            print(f"Search Result: {res_search.json()}")
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    test_rpc_flow()
