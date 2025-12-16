
import os
import sys
# import pytest (Not needed for this simple script)
from fastapi.testclient import TestClient
import asyncio

# Ensure root
sys.path.append(os.getcwd())

# Needs AsyncPG patch or we test logic only?
# TestClient is sync, but app is async. 
# TestClient handles async app via starlette.testclient.

# We need to setup DB for API tests.
# test_async_core.py does it manually.
# For API, lifespan runs AsyncDatabase.initialize().
# So TestClient(app) should work if we can connect to DB.

from core.http_fastapi import app
from core.db_async import AsyncDatabase

client = TestClient(app)

def test_api_flow():
    print("--- Testing REST API ---")
    
    # 1. List Users (Needs DB)
    # This might fail if DB pool is not initialized inside TestClient context 
    # OR if we don't use 'with TestClient(app) as client:' to trigger lifespan?
    
    with TestClient(app) as client:
        # Create user via Schema? 
        # API requires env which requires DB connection.
        # AsyncDatabase.initialize() happens in lifespan.
        
        # Check Swagger
        resp = client.get("/docs")
        print(f"Swagger UI Status: {resp.status_code}")
        if resp.status_code != 200:
             print("FAIL: Swagger UI not found")
             return
             
        # Check API Spec
        resp = client.get("/openapi.json")
        print(f"OpenAPI Spec Status: {resp.status_code}")
        if resp.status_code != 200:
             print("FAIL: OpenAPI Spec not found")
             return
             
        # Mocking or expecting DB avail
        # If DB is running (it is), this should hit res.users
        try:
             resp = client.get("/api/res.users")
             print(f"List Users Status: {resp.status_code}")
             if resp.status_code == 200:
                 data = resp.json()['data']
                 print(f"Found {len(data)} users")
             else:
                 print(f"FAIL: List Users error: {resp.text}")
        except Exception as e:
             print(f"FAIL: Exception calling API: {e}")

if __name__ == "__main__":
    test_api_flow()
