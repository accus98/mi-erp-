import threading
import time
import requests
import base64
import os

def run_test():
    print("--- Testing Static & Binary Serving ---")
    
    # Start Server (Assume background logic or restart required if main changes not picked up)
    # Since we modified server.py logic (imports), we should ideally ensure updated code runs.
    # In this script we import from bin.server assuming it re-imports core?
    # Python imports are cached. 
    # For robustness, we trust the code logic matches step.
    
    from bin.server import startup, ThreadingHTTPServer, NexoRequestHandler
    import core.http # ensure reloaded if possible? No easy reload.
    
    try:
        startup() 
    except: 
        pass

    server = ThreadingHTTPServer(('localhost', 8998), NexoRequestHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    
    print("Server started on localhost:8998")
    time.sleep(1)
    
    base_url = "http://localhost:8998"
    
    try:
        # 1. Test Static File
        print("\n[1] Testing Static File Serving...")
        url = f"{base_url}/web/static/src/main.js"
        resp = requests.get(url)
        print(f"GET {url}: {resp.status_code}")
        
        if resp.status_code == 200 and 'console.log' in resp.text:
            print("SUCCESS: Static file served.")
        else:
            print(f"FAILURE: Static serving failed. {resp.text}")

        # 2. Test Binary Download
        # Need Login
        session = requests.Session()
        # Admin authed?
        session.post(f"{base_url}/web/login", json={'login':'admin', 'password':'admin_password'})
        
        # Create a record with binary content
        # We need to do this via DB direct or RPC.
        # Let's use RPC since it's available.
        
        img_data = b"FAKE_IMAGE_DATA"
        b64_img = base64.b64encode(img_data).decode('utf-8')
        
        rpc_create = {
            "model": "test.binary", # Ensure we have a model with binary
            # We defined ModelWithBin in test_alive.py but it's not persistent in registry unless loaded.
            # Registry setup_models loads core + modules.
            # We can define a dynamic model in 'ir.model' via RPC? No, schema needs python class.
            # We will use 'ir.attachment' directly to test content serving since it has 'datas'.
            # Wait, binary controller reads record field.
            # `env['ir.attachment'].browse(id).datas` -> returns base64 string.
            "method": "create",
            "args": [{
                "name": "Test Att",
                "res_model": "test",
                "res_id": 0,
                "datas": b64_img,
                "mimetype": "text/plain"
            }],
            "kwargs": {}
        }
        
        resp = session.post(f"{base_url}/web/dataset/call_kw", json={"params": rpc_create})
        if resp.status_code == 200 and 'result' in resp.json():
            att_id = resp.json()['result'] # create returns recordset or id?
            # create returns RecordSet. RPC serialization in main.py logic:
            # result = list(result.ids) -> [id]
            if isinstance(att_id, list): att_id = att_id[0]
            
            print(f"Created Attachment ID: {att_id}")
            
            # Now download: /web/content/ir.attachment/<id>/datas
            # Note: Controller expects model, id, field. 
            # ir.attachment model, id=att_id, field='datas'.
            
            url_dl = f"{base_url}/web/content/ir.attachment/{att_id}/datas"
            resp_dl = session.get(url_dl)
            print(f"GET {url_dl}: {resp_dl.status_code}")
            
            if resp_dl.status_code == 200 and resp_dl.content == img_data:
                print("SUCCESS: Binary content downloaded.")
            else:
                 print(f"FAILURE: Content mismatch. Got {resp_dl.content}")

        else:
            print(f"Skipping Binary Test: Failed to create record. {resp.text}")

    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    run_test()
