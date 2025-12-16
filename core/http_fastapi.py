import os
import mimetypes
from fastapi import FastAPI, Request, Response, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import re
import uuid

# Import original http to get ROUTES and Session logic
from core.http import ROUTES, Session, Response as NexusResponse

# Import middleware/deps
from core.db import Database
from core.env import Environment

# --- Module Loading Logic ---
def load_modules():
    print("Loading Modules...")
    import sys
    
    # 1. Core Controllers
    import core.controllers.main
    import core.controllers.binary
    
    # 2. Addons Loading
    addons_path = os.path.join(os.getcwd(), 'addons')
    if os.path.exists(addons_path) and os.path.isdir(addons_path):
        sys.path.append(addons_path)
        for item in os.listdir(addons_path):
            if item.startswith('.'): continue
            mod_path = os.path.join(addons_path, item)
            if os.path.isdir(mod_path):
                # Try import
                try:
                    # We assume addons.module_name structure if using namespaces
                    # OR just adding addons to sys.path allows 'import module_name'
                    # But better: import addons.module_name
                    import importlib
                    importlib.import_module(f"addons.{item}")
                    # Also try to import models/controllers submodules if they exist implicitly?
                    # Odoo logic is __init__.py imports them.
                    # We assume __init__.py handles it.
                    print(f"Loaded addon: {item}")
                except Exception as e:
                    print(f"Failed to load addon {item}: {e}")

load_modules()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Open DB Pool
    # Database.connect() # logic in db.py handles pool init on first connect
    yield
    # Shutdown: Close Pool
    Database.close_all()

app = FastAPI(lifespan=lifespan)

# Adapter for Nexus Request
class NexusRequest:
    def __init__(self, request: Request, session: Session, params: dict):
        self._request = request
        self.session = session
        self.params = params
        self.json = {}
        self.query_params = dict(request.query_params)
        self.path = request.url.path
        
    async def load_body(self):
        try:
            self.json = await self._request.json()
        except:
            pass

# Dependency for Session
async def get_session(request: Request):
    sid = request.cookies.get('session_id')
    session = None
    if sid:
        session = Session.load(sid)
    
    if not session:
        session = Session.new()
    
    # Check Lang from Cookie if not in context
    if 'lang' not in session.context:
        # TODO: Get from browser Accept-Language or Cookie
        pass
        
    return session

# Dynamic Router Logic
# We can't easily use app.get() decorator for existing dynamic dictionary ROUTES.
# Instead, we catch-all or register them at startup.
# Registering at startup is better for Swagger UI.

def convert_route_path(path):
    # <int:id> -> {id}
    # <string:name> -> {name}
    # <id> -> {id}
    new_path = re.sub(r'<int:(\w+)>', r'{\1}', path)
    new_path = re.sub(r'<string:(\w+)>', r'{\1}', new_path)
    new_path = re.sub(r'<(\w+)>', r'{\1}', new_path)
    return new_path

# Register Routes
for path, info in ROUTES.items():
    nx_func = info['func']
    auth_mode = info['auth']
    fastapi_path = convert_route_path(path)
    
    # Wrapper function generator
    def make_handler(func, auth):
        async def handler(request: Request, response: Response, session: Session = Depends(get_session)):
            # Auth Check
            if auth == 'user' and not session.uid:
                 return JSONResponse(status_code=403, content={"error": "Login Required"})

            # DB Connection
            conn = Database.connect()
            try:
                cr = Database.cursor(conn)
                uid = session.uid
                env = Environment(cr, uid=uid, context=session.context)
                
                # Prepare Nexus Request
                params = request.path_params
                nx_req = NexusRequest(request, session, params)
                await nx_req.load_body()
                
                # Call Original Controller
                # Original controllers are sync functions usually
                # FastAPI runs them in threadpool if not async def
                nx_resp = func(nx_req, env)
                
                conn.commit()
                
                # Convert Response
                if isinstance(nx_resp, NexusResponse):
                    # headers
                    for k, v in nx_resp.headers.items():
                        response.headers[k] = v
                    # cookies
                    for k, v in nx_resp.cookies.items():
                        # SimpleCookie to Starlette logic
                        # Simplified:
                         response.set_cookie(key=k, value=v.value, httponly=v['httponly'], path=v['path'])
                    
                    # session cookie
                    response.set_cookie('session_id', session.sid, httponly=True)
                    
                    return Response(content=nx_resp.render(), status_code=nx_resp.status, media_type=nx_resp.content_type)
                elif isinstance(nx_resp, (dict, list)):
                     return JSONResponse(content=nx_resp)
                else:
                     return HTMLResponse(content=str(nx_resp))

            except Exception as e:
                conn.rollback()
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                return JSONResponse(status_code=500, content={"error": str(e)})
            finally:
                Database.release(conn)
        return handler

    # Register with supporting methods (GET/POST)
    # Original framework didn't distinguish, so allow all
    app.add_api_route(fastapi_path, make_handler(nx_func, auth_mode), methods=["GET", "POST", "PUT", "DELETE"])

# Static Files Middleware
# Pattern: /<module>/static/<file_path>
# FastAPI StaticFiles mounts to a specific path prefix.
# We need to mount each module? Or use a generic catch-all for static?
# Root mount might conflict with greedy regex.
# Let's check addons dir.
import os
addons_path = os.path.join(os.getcwd(), 'addons')
if os.path.exists(addons_path):
    # We can iterate modules and mount /mod/static
    for mod in os.listdir(addons_path):
        mod_static = os.path.join(addons_path, mod, 'static')
        if os.path.isdir(mod_static):
            app.mount(f"/{mod}/static", StaticFiles(directory=mod_static), name=f"{mod}_static")

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)
