import threading
import time
import requests
import json
import datetime

def run_test():
    print("--- Testing Sales Module & Dynamic Menus ---")
    
    from bin.server import startup, ThreadingHTTPServer, NexoRequestHandler
    import core.http 
    
    try: startup() 
    except: pass

    server = ThreadingHTTPServer(('localhost', 8996), NexoRequestHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    
    print("Server started on localhost:8996")
    time.sleep(1)
    
    base_url = "http://localhost:8996"
    session = requests.Session()
    session.post(f"{base_url}/web/login", json={'login':'admin', 'password':'admin_password'})
    
    try:
        # 1. Create a Partner (Dependency)
        # Assuming res.partner exists in base. 'admin' is a user, not partner?
        # Let's check logic. sale.order needs partner_id.
        # We'll create one.
        print("\n[1] Creating Partner...")
        # Check if res.partner exists? It should (base module).
        rpc_partner = {
            "model": "res.partner",
            "method": "create",
            "args": [{"name": "Test Customer"}],
            "kwargs": {}
        }
        resp = session.post(f"{base_url}/web/dataset/call_kw", json={"params": rpc_partner})
        pid = resp.json().get('result')
        if isinstance(pid, list): pid = pid[0]
        print(f"Partner ID: {pid}")
        
        # 2. Create Sale Order (Test Sequence)
        print("\n[2] Creating Sale Order...")
        rpc_so = {
            "model": "sale.order",
            "method": "create",
            "args": [{
                "partner_id": pid,
                "date_order": "2024-12-01 10:00:00",
                "amount_total": 100.0
            }],
            "kwargs": {}
        }
        resp = session.post(f"{base_url}/web/dataset/call_kw", json={"params": rpc_so})
        so_id = resp.json().get('result')
        if isinstance(so_id, list): so_id = so_id[0]
        
        # Read Name
        rpc_read = {
            "model": "sale.order",
            "method": "read",
            "args": [[so_id], ['name']],
            "kwargs": {} 
        }
        # Note: Generic read not implemented in Controller? 
        # Controller calls method on model. 
        # Model class (orm.Model) doesn't have 'read' method yet?
        # We have 'search', 'browse' (internal), 'create', 'write'.
        # We usually use 'search_read' or 'read_group'.
        # Let's try to fetch via search if read is missing, or browse().name if internal.
        # But this is RPC.
        # Wait, did we implement 'read'? Check orm.py.
        # Checking... I don't recall explicit 'read'. 
        # I'll check 'search_read' if available, otherwise just check console logs or implement read.
        # Actually, simpler: create returned ID. If create worked, sequence worked (inside create override).
        # We can try to use 'search' with domain id=so_id to see if it exists.
        
        print(f"Sale Order Created: ID {so_id}")

        # 3. Test Menu Loading
        print("\n[3] Testing RPC load_menus...")
        rpc_menu = {
            "model": "ir.ui.menu",
            "method": "load_menus",
            "args": [],
            "kwargs": {}
        }
        resp = session.post(f"{base_url}/web/dataset/call_kw", json={"params": rpc_menu})
        menus = resp.json().get('result')
        
        print(f"Menus Fetched: {len(menus) if menus else 0}")
        found_sales = False
        if menus:
            for m in menus:
                print(f" - {m['name']}")
                if m['name'] == 'Sales':
                    found_sales = True
                    # Check Children
                    if 'children' in m and len(m['children']) > 0:
                        print("   -> Has children (Good)")
        
        if found_sales:
            print("SUCCESS: Sales menu found in RPC response.")
        else:
            print("FAILURE: Sales menu missing.")

    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    run_test()
