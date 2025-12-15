import threading
import time
import requests
import json
import traceback

def run_test():
    print("--- Testing HTTP Layer (The Voice) ---")
    
    # Start Server in Background
    # We can't easily start the real server in same process due to blocking.
    # We will assume server is started separately or we try to thread it here.
    # But bin/server.py imports everything and starts serving in __main__. 
    # We can import startup and RequestHandler.
    
    from bin.server import startup, ThreadingHTTPServer, NexoRequestHandler
    
    # Run startup first to init DB/Registry
    try:
        startup() # This triggers DB sync
    except Exception as e:
        print(f"Startup Failed: {e}")
        return # Cannot test if startup fails

    # Start Server Thread
    server = ThreadingHTTPServer(('localhost', 8999), NexoRequestHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    
    print("Server started on localhost:8999")
    time.sleep(2) # Wait for modules
    
    base_url = "http://localhost:8999"
    session = requests.Session()
    
    try:
        # 1. Test Login
        print("\n[1] Testing Login...")
        # Need a user. 'admin' / 'admin' usually created by bootstrap if not present?
        # We don't have auto-bootstrap of admin data yet in `addons/base` or `setup_models`.
        # We might need to create user manually via DB for test to work.
        
        # Inject Admin User for test
        from core.db import Database
        from core.env import Environment
        conn = Database.connect()
        cr = Database.cursor(conn)
        env = Environment(cr, uid=1)
        Users = env['res.users']
        if not Users.search([('login','=','admin')]):
             Users.create({'name': 'Admin', 'login': 'admin', 'password': 'admin_password'})
             print("Created Admin User")
        else:
             # Ensure password matches hash logic.
             # We can't update password easily if we don't know plain text.
             # Let's hope previous setup or create works.
             # If create fails (found), we try login.
             pass
        conn.commit()
        conn.close()

        resp = session.post(f"{base_url}/web/login", json={
            'login': 'admin',
            'password': 'admin_password'
        })
        
        print(f"Login Response: {resp.status_code} {resp.text}")
        if resp.status_code == 200 and 'session_id' in resp.json().get('result', {}):
            print("SUCCESS: Login successful, Cookie received.")
        else:
            print("FAILURE: Login failed.")
            server.shutdown()
            return
            
        # 2. Test JSON-RPC
        print("\n[2] Testing call_kw (search_read)...")
        
        # Search Partners
        rpc_payload = {
            "model": "res.partner",
            "method": "search",
            "args": [[]], # Empty domain
            "kwargs": {}
        }
        
        resp = session.post(f"{base_url}/web/dataset/call_kw", json={
            "params": rpc_payload
        })
        
        print(f"RPC Response: {resp.status_code} {resp.text}")
        
        if resp.status_code == 200 and 'result' in resp.json():
            res = resp.json()['result']
            print(f"Result (IDs): {res}")
            print("SUCCESS: RPC Call works.")
        else:
            print("FAILURE: RPC Call failed.")

    except Exception as e:
        print(f"Test Error: {e}")
        traceback.print_exc()
    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    run_test()
