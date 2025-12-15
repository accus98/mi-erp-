import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.registry import Registry
from core.db import Database
from core.http import dispatch
import core.controllers.main # Register routes implementation
import core.controllers.binary

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class NexoRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        dispatch(self)
        
    def do_POST(self):
        dispatch(self)
        
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        # Override to reduce noise or custom log
        sys.stderr.write("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format%args))

def startup():
    print("Loading modules...")
    try:
        import core.models # Load Meta-Models
        
        from core.modules.module_loader import ModuleLoader
        
        # Synchronize Registry (Core models) first
        conn = Database.connect()
        cr = conn.cursor()
        try:
            Registry.setup_models(cr)
            
            # Create Env for Loader (needs uid=1 for creation)
            from core.env import Environment
            env = Environment(cr, uid=1)
            
            conn.commit()
            
            # DEBUG: Check tables
            cr.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0] for r in cr.fetchall()]
            print(f"DEBUG: Current Tables: {tables}")

            # Load Addons (Topological)
            addons_path = os.path.join(os.getcwd(), 'addons')
            ModuleLoader.load_addons(addons_path, env)
            
            conn.commit()
            
            # Ensure Admin User Exists
            try:
                Users = env['res.users']
                admins = Users.search([('login', '=', 'admin')])
                if not admins:
                    print("Creating default admin user...")
                    Users.create({
                        'name': 'Administrator',
                        'login': 'admin',
                        'password': 'admin'
                    })
                    conn.commit()
            except Exception as e:
                # Might fail if base module not loaded yet or res.users issue
                print(f"Admin creation warning: {e}")
        except Exception as e:
            conn.rollback()
            print(f"Sync/Load Failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            Database.release(conn)
            
        print("System Ready. Listening on 0.0.0.0:8000")
        
    except Exception as e:
        print(f"Error loading modules: {e}")

    # Start Cron Thread
    from core.models.ir_cron import IrCron
    db_params = {}
    cron_thread = threading.Thread(target=IrCron.runner_loop, args=(db_params,), daemon=True)
    cron_thread.start()
    print("Cron Heartbeat active.")

if __name__ == "__main__":
    startup()
    server = ThreadingHTTPServer(('0.0.0.0', 8000), NexoRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
