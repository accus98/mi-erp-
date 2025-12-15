
import requests
import json
import sys

def debug_view_info():
    url = "http://localhost:8000/web/dataset/call_kw"
    
    session = requests.post("http://localhost:8000/web/login", 
        json={"params": {"login": "admin", "password": "admin"}})
    
    print("\n--- Get View Info Sale Order (Tree) ---")
    payload = {
        "jsonrpc": "2.0", "method": "call",
        "params": {
            "model": "sale.order",
            "method": "get_view_info",
            "args": [], 
            "kwargs": {
                "view_type": "tree"
            }
        }, "id": 1
    }
    
    res = requests.post(url, json=payload, cookies=session.cookies).json()
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    debug_view_info()
