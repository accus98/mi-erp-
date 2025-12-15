
import requests
import json
import sys

def debug_search_read():
    url = "http://localhost:8000/web/dataset/call_kw"
    
    # 1. Login
    session = requests.post("http://localhost:8000/web/login", 
        json={"params": {"login": "admin", "password": "admin"}})
    
    if session.status_code != 200:
        print("Login failed")
        return

    print("Login successful.")
    
    # 2. Search Read Sale Order
    print("\n--- Search Read Sale Order ---")
    payload = {
        "jsonrpc": "2.0", "method": "call",
        "params": {
            "model": "sale.order",
            "method": "search_read",
            "args": [], 
            "kwargs": {
                "domain": [],
                "fields": ["name", "state", "partner_id", "date_order", "amount_total"]
            }
        }, "id": 1
    }
    
    res = requests.post(url, json=payload, cookies=session.cookies).json()
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    debug_search_read()
