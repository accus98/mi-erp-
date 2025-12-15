import threading
import time
import requests
import json

def run_test():
    print("--- Testing Sequences & RPC Hardening ---")
    
    from bin.server import startup, ThreadingHTTPServer, NexoRequestHandler
    import core.http 
    
    try: startup() 
    except: pass

    server = ThreadingHTTPServer(('localhost', 8997), NexoRequestHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    
    print("Server started on localhost:8997")
    time.sleep(1)
    
    base_url = "http://localhost:8997"
    session = requests.Session()
    session.post(f"{base_url}/web/login", json={'login':'admin', 'password':'admin_password'})
    
    try:
        # 1. Create Sequence via RPC
        print("\n[1] Creating Sequence 'TEST_SEQ'...")
        rpc_create = {
            "model": "ir.sequence",
            "method": "create",
            "args": [{
                "name": "Test Sequence",
                "code": "TEST_SEQ",
                "prefix": "TST/%(year)s/",
                "padding": 3
            }],
            "kwargs": {}
        }
        session.post(f"{base_url}/web/dataset/call_kw", json={"params": rpc_create})
        
        # 2. Generate Number
        print("\n[2] Generating Next Number...")
        rpc_next = {
            "model": "ir.sequence",
            "method": "next_by_code",
            "args": ["TEST_SEQ"],
            "kwargs": {}
        }
        resp = session.post(f"{base_url}/web/dataset/call_kw", json={"params": rpc_next})
        print(f"Next Resp: {resp.text}")
        
        result = resp.json().get('result')
        if "TST/" in str(result):
            print(f"SUCCESS: Generated {result}")
        else:
            print("FAILURE: Sequence generation failed.")

        # 3. Test RPC Hardening (Exception)
        print("\n[3] Testing RPC Error Handling...")
        rpc_fail = {
            "model": "ir.sequence",
            "method": "non_existent_method", # This should raise AttributeError
            "args": [],
            "kwargs": {}
        }
        resp = session.post(f"{base_url}/web/dataset/call_kw", json={"params": rpc_fail})
        print(f"Error Resp Code: {resp.status_code}") # Should be 200 (JSON-RPC protocol)
        data = resp.json()
        
        if 'error' in data and 'Odoo Server Error' in data['error']['message']:
            print("SUCCESS: Caught exception gracefully.")
            print(f"Debug: {data['error']['data']['message']}")
        else:
            print("FAILURE: Did not return structured error.")

    except Exception as e:
        print(f"Test Error: {e}")
    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    run_test()
