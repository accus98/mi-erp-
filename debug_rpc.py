
import requests
import json
import sys

def debug_rpc():
    url = "http://localhost:8000/web/dataset/call_kw"
    
    # 1. Login to get session
    session = requests.post("http://localhost:8000/web/login", 
        json={"params": {"login": "admin", "password": "admin"}})
    
    if session.status_code != 200:
        print("Login failed")
        return

    print("Login successful. Session cookies:", session.cookies)
    
    # 2. Call load_menus
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "ir.ui.menu",
            "method": "load_menus",
            "args": [],
            "kwargs": {}
        },
        "id": 1
    }
    
    response = requests.post(url, json=payload, cookies=session.cookies)
    if response.status_code == 200:
        res = response.json()
        print("\n--- load_menus Result (Tree) ---")
        # Recursively find "Orders"
        def find_orders(menus):
            for m in menus:
                if m['name'] == 'Orders' or m['name'] == 'Pedidos':
                    print(f"FOUND MENU: {m['name']}")
                    print(f"ACTION: {m.get('action')}")
                    print(f"ID: {m['id']}")
                    return
                if 'children' in m:
                    find_orders(m['children'])
        
        if 'result' in res:
            find_orders(res['result'])
        else:
            print("Error in result:", res)
    else:
        print("RPC Failed", response.status_code)

if __name__ == "__main__":
    debug_rpc()
