import requests
import json

BASE_URL = "http://localhost:8000"

def test_csrf():
    print("Test: CSRF Protection")
    
    # 1. Login to get Session
    s = requests.Session()
    # Assume admin/admin works or needs recovery?
    # Actually server is running, admin/admin should be valid if recovered earlier.
    # But wait, python script cannot use 'admin' password if it was hashed?
    # Using 'admin' as password if demo data loaded.
    # Or I can use 'admin' password if recover was run.
    # Let's try standard login.
    
    resp = s.post(f"{BASE_URL}/web/login", json={"params": {"login": "admin", "password": "admin"}})
    print(f"Login Status: {resp.status_code}")
    if resp.status_code != 200:
        print("Login Failed. Cannot proceed.")
        return

    # 2. Get CSRF Token
    resp = s.get(f"{BASE_URL}/web/session/token") # GET is safe
    if resp.status_code != 200:
        print(f"Failed to get token: {resp.text}")
        return
        
    token_data = resp.json()
    csrf_token = token_data['result']['token']
    print(f"Got Token: {csrf_token}")
    
    # 3. Test Protected Endpoint (e.g. call_kw write/create) without header
    # call_kw is POST.
    payload = {
        "params": {
            "model": "res.users",
            "method": "search_read",
            "args": [],
            "kwargs": {}
        }
    }
    
    # Request WITHOUT header
    print("Testing Missing Header...")
    resp = s.post(f"{BASE_URL}/web/dataset/call_kw", json=payload)
    print(f"Response: {resp.status_code}")
    if resp.status_code == 403:
        print("PASS: Request without header was blocked.")
    else:
        print(f"FAIL: Request without header was NOT blocked ({resp.status_code}).")

    # Request WITH INVALID header
    print("Testing Invalid Header...")
    resp = s.post(f"{BASE_URL}/web/dataset/call_kw", json=payload, headers={"X-CSRF-Token": "invalid-token"})
    print(f"Response: {resp.status_code}")
    if resp.status_code == 403:
        print("PASS: Request with invalid header was blocked.")
    else:
        print(f"FAIL: Request with invalid header was NOT blocked.")
        
    # Request WITH VALID header
    print("Testing Valid Header...")
    resp = s.post(f"{BASE_URL}/web/dataset/call_kw", json=payload, headers={"X-CSRF-Token": csrf_token})
    print(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        print("PASS: Request with valid header succeeded.")
    else:
        print(f"FAIL: Request with valid header FAILED ({resp.status_code}): {resp.text}")

if __name__ == "__main__":
    try:
        test_csrf()
    except Exception as e:
        print(f"Test Failed: {e}")
