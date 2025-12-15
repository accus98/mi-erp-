import sys
import os
from fastapi.testclient import TestClient
from bin.server import app
from core.db import Database
from addons.base.models.res_users import ResUsers

# Add current directory to path
sys.path.append(os.getcwd())

client = TestClient(app)

from core.env import Environment

def test_auth_flow():
    print("--- Testing Auth ---")
    
    # 1. Init DB
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        # Ensure tables
        ResUsers._auto_init(cr)
        
        # API v2 Creation
        env = Environment(cr, uid=1)
        UserProxy = env['res.users']
        
        existing = UserProxy.search([('login', '=', 'admin')])
        if not existing:
             UserProxy.create({'login': 'admin', 'password': 'superpassword'})
             print("Admin user created.")
        else:
             print("Admin user already exists.")
             
        conn.commit()
    except Exception as e:
        print(f"DB Init failed (expected if no local DB): {e}")
        return

    # 2. Login
    print("\n[POST] /api/login")
    response = client.post("/api/login", json={"login": "admin", "password": "superpassword"})
    print(f"Login Response: {response.status_code} {response.json()}")
    
    if response.status_code != 200:
        print("Login failed, stopping.")
        return

    token = response.json()['access_token']
    
    # 3. Protected Call
    print("\n[POST] /api/call (Authentication)")
    headers = {"Authorization": f"Bearer {token}"}
    
    payload = {
        "model": "res.partner",
        "method": "search",
        "args": [[]]
    }
    
    resp_call = client.post("/api/call", json=payload, headers=headers)
    print(f"Protected API Response: {resp_call.status_code}")

    if resp_call.status_code == 200:
        print("SUCCESS: Authenticated RPC access confirmed.")
    else:
        print(f"FAILURE: {resp_call.json()}")

if __name__ == "__main__":
    test_auth_flow()
