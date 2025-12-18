import os
import mimetypes
from fastapi import FastAPI, Request, Response, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import re
import uuid

# Import original http to get ROUTES and Session logic
from core.http import ROUTES, Response as NexusResponse
from core.cache import Cache

# Import middleware/deps
from core.db_async import AsyncDatabase
from core.env import Environment
from core.api.router import api_router

# --- Module Loading Logic ---
def load_modules():
    print("Loading Modules...")
    import sys
    import importlib
    
    # 1. Core Controllers
    import core.controllers.main
    import core.controllers.binary
    
    # 2. Core Models (Explicitly load introspection models)
    models_path = os.path.join(os.getcwd(), 'core', 'models')
    if os.path.exists(models_path):
        for item in os.listdir(models_path):
            if item.endswith('.py') and not item.startswith('__'):
                mod_name = item[:-3]
                try:
                    importlib.import_module(f"core.models.{mod_name}")
                    print(f"Loaded core model: {mod_name}")
                except Exception as e:
                    print(f"Failed to load core model {mod_name}: {e}")

    # 3. Addons Loading
    addons_path = os.path.join(os.getcwd(), 'addons')
    if os.path.exists(addons_path) and os.path.isdir(addons_path):
        sys.path.append(addons_path)
        
        from core.module_graph import load_modules_topological
        ordered_addons = load_modules_topological(addons_path)
        print(f"Loading Addons in Order: {ordered_addons}")
        
        for item in ordered_addons:
            try:
                import importlib
                importlib.import_module(f"addons.{item}")
                print(f"Loaded addon: {item}")
            except Exception as e:
                print(f"Failed to load addon {item}: {e}")

load_modules()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Open DB Pool
    await AsyncDatabase.initialize()
    yield
    # Shutdown: Close Pool
    await AsyncDatabase.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)

# Async Session Logic
class Session:
    def __init__(self, sid):
        self.sid = sid
        self.uid = None
        self.login = None
        self.context = {}
        self._dirty = False # Not used in Redis impl, but kept for compat
        
    @classmethod
    def new(cls):
        sid = str(uuid.uuid4())
        sess = cls(sid)
        sess.csrf_token = str(uuid.uuid4()) # Generate CSRF Token
        sess.save()
        return sess

    @classmethod
    def load(cls, sid):
        print(f"DEBUG_SESSION: Loading {sid}")
        data = Cache.get(f"session:{sid}")
        print(f"DEBUG_SESSION: Data for {sid}: {data}")
        if data:
            sess = cls(sid)
            sess.uid = data.get('uid')
            sess.login = data.get('login')
            sess.context = data.get('context', {})
            sess.csrf_token = data.get('csrf_token') or str(uuid.uuid4()) # Auto-heal if missing
            return sess
        return None

    
    def rotate(self):
        """
        Regenerate Session ID to prevent Fixation Attacks.
        Moves data to new ID and deletes old one.
        CSRF Token is *preserved* or *rotated*?
        Usually preserved to allow in-flight requests, or rotated for max security.
        Let's rotate it too for fresh login state.
        """
        old_sid = self.sid
        # Create new ID
        self.sid = str(uuid.uuid4())
        self.csrf_token = str(uuid.uuid4()) # Rotate CSRF
        # Save new
        self.save()
        # Delete old
        Cache.delete(f"session:{old_sid}")
        print(f"DEBUG_SESSION: Rotated {old_sid} -> {self.sid}")

    def save(self):
        data = {
            'uid': self.uid,
            'login': self.login,
            'context': self.context,
            'csrf_token': getattr(self, 'csrf_token', None)
        }
        # TTL 1 day
        Cache.set(f"session:{self.sid}", data, ttl=86400)

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
    print(f"DEBUG_SESSION: Middleware Cookie SID: {sid}")
    session = None
    if sid:
        session = Session.load(sid)
    
    if not session:
        print("DEBUG_SESSION: Creating NEW Session")
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
            # 1. CSRF Protection (Audit Remediation)
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                # Exempt login
                if request.url.path == "/web/login":
                    pass
                else:
                    csrf_header = request.headers.get("X-CSRF-Token")
                    if not csrf_header or csrf_header != session.csrf_token:
                         return JSONResponse(status_code=403, content={"error": "CSRF Validation Failed. Please refresh the page."})

            # 2. Auth Check
            if auth == 'user' and not session.uid:
                 return JSONResponse(status_code=403, content={"error": "Login Required"})

            # Async DB Connection (Transaction Managed by acquire context)
            try:
                # acquire() yields a cursor inside a transaction.
                # If we exit block without error -> Commit. 
                # If we raise exception -> Rollback.
                async with AsyncDatabase.acquire() as cr:
                    uid = session.uid
                    env = Environment(cr, uid=uid, context=session.context)
                    
                    # Async Prefetch to support Sync Properties (env.user, env.company) in Controllers
                    if uid:
                        await env.prefetch_user()
                    
                    # Prepare Nexus Request
                    params = request.path_params
                    nx_req = NexusRequest(request, session, params)
                    await nx_req.load_body()
                    
                    # Call Controller
                    # Controllers can be sync (old) or async (new).
                    import inspect
                    if inspect.iscoroutinefunction(func):
                        nx_resp = await func(nx_req, env)
                    else:
                        # Fallback for legacy sync controllers that DO NOT use ORM logic?
                        # If a sync controller uses ORM, it will crash.
                        print(f"WARNING: Sync Controller called: {func.__name__}. Migration Required.")
                        nx_resp = func(nx_req, env)
                        if inspect.iscoroutine(nx_resp):
                             nx_resp = await nx_resp
                    
                    # Convert Response
                    # Convert Response
                    if isinstance(nx_resp, NexusResponse):
                        final_response = Response(content=nx_resp.render(), status_code=nx_resp.status, media_type=nx_resp.content_type)
                        
                        # headers
                        for k, v in nx_resp.headers.items():
                            final_response.headers[k] = v
                        # cookies
                        for k, v in nx_resp.cookies.items():
                             final_response.set_cookie(key=k, value=v.value, httponly=v['httponly'], path=v['path'])
                        
                        # session cookie
                        # Ensure samesite='lax' for localhost dev. Secure if HTTPS.
                        is_secure = os.getenv('SESSION_SECURE', 'False').lower() == 'true'
                        final_response.set_cookie('session_id', session.sid, httponly=True, samesite='lax', secure=is_secure)
                        
                        return final_response
                    elif isinstance(nx_resp, (dict, list)):
                         return JSONResponse(content=nx_resp)
                    else:
                         return HTMLResponse(content=str(nx_resp))

            except Exception as e:
                # Transaction Rolled back by async with block exit
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
                return JSONResponse(status_code=500, content={"error": str(e)})
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
