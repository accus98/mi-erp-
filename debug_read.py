
import requests
import json
import sys

def debug_read():
    url = "http://localhost:8000/web/dataset/call_kw"
    
    # 1. Login
    session = requests.post("http://localhost:8000/web/login", 
        json={"params": {"login": "admin", "password": "admin"}})
    
    if session.status_code != 200:
        print("Login failed")
        return

    # 2. Read Action 1
    print("\n--- Reading Action 1 ---")
    payload_1 = {
        "jsonrpc": "2.0", "method": "call",
        "params": {
            "model": "ir.actions.act_window",
            "method": "read",
            "args": [[1]], 
            "kwargs": {}
        }, "id": 1
    }
    res1 = requests.post(url, json=payload_1, cookies=session.cookies).json()
    print(res1)

    # 3. Read Action 11
    print("\n--- Reading Action 11 ---")
    payload_11 = {
         "jsonrpc": "2.0", "method": "call",
         "params": {
             "model": "ir.actions.act_window",
             "method": "read",
             "args": [[11]], 
             "kwargs": {}
         }, "id": 2
    }
    res11 = requests.post(url, json=payload_11, cookies=session.cookies).json()
    print(res11)

if __name__ == "__main__":
    debug_read()
