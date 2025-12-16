
import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, Depends, status
from fastapi.responses import JSONResponse, HTMLResponse, Response as FastAPIResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Core Imports
from core.db import Database
from core.env import Environment
from core.registry import Registry
from core.http import ROUTES, Session  # We still use the ROUTES registry
from core.logger import logger # Structured Logging

# Load Controllers to populate ROUTES
# In a real dynamic loader, we'd do this differently
import core.controllers.main # Ensures dispatch logic is loaded

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("🚀 Nexo ERP (FastAPI) Starting...")
    Database.connect()
    
    # logic migrated from bin/server.py
    # logic migrated from bin/server.py
    logger.info("Loading modules...")
    try:
        import core.models # Load Meta-Models
        # Also need controllers imports here/top-level to ensure routes registered?
        # imports are at top of file
        
        from core.modules.module_loader import ModuleLoader
        
        conn = Database.connect()
        cr = conn.cursor()
        try:
            Registry.setup_models(cr)
            
            # Create Env for Loader (needs uid=1 for creation)
            from core.env import Environment
            env = Environment(cr, uid=1)
            
            # Load Addons (Topological)
            base_path = os.getcwd()
            addons_path = os.path.join(base_path, 'addons')
            ModuleLoader.load_addons(addons_path, env)
            
            conn.commit()
            
            # Ensure Admin User Exists
            try:
                Users = env['res.users']
                admins = Users.search([('login', '=', 'admin')])
                if not admins:
                    logger.info("Creating default admin user...")
                    Users.create({
                        'name': 'Administrator',
                        'login': 'admin',
                        'password': 'admin'
                    })
                    conn.commit()
            except Exception as e:
                logger.warning(f"Admin creation warning: {e}")

        except Exception as e:
            conn.rollback()
            logger.error(f"Sync/Load Failed: {e}", exc_info=True)
            import traceback
            traceback.print_exc()
        finally:
            # Release the temporary connection used for loading
            Database.release(conn)
            
            
    except Exception as e:
         logger.critical(f"Startup Critical Error: {e}", exc_info=True)

    # Start Cron (Daemon Thread)
    # DEPRECATED: Cron is now managed by core/worker.py (Async Jobs)
    # try:
    #     from core.models.ir_cron import IrCron
    #     import threading
    #     cron_thread = threading.Thread(target=IrCron.runner_loop, args=({},), daemon=True)
    #     cron_thread.start()
    #     logger.info("Cron Heartbeat active.")
    # except Exception as e:
    #     logger.error(f"Cron Start Failed: {e}")

    yield
    
    # --- Shutdown ---
    # --- Shutdown ---
    logger.info("🛑 Shutting down...")
    Database.close_all()
    Database.close_all()

app = FastAPI(lifespan=lifespan, title="Nexo ERP", version="2.0 Enterprise")

# CORS (Optional but good for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "*" # Fallback for dev, but browsers might ignore if creds=True
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Server Logic Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"message": f"Server Logic Error: {str(exc)}", "type": str(type(exc))}}
    )

# --- Dependencies ---

class RequestContext:
    """Wrapper to mimic the old 'req' object expected by controllers"""
    def __init__(self, request: Request, session: Session, json_body: dict = None):
        self._request = request
        self.session = session
        self.json = json_body or {}
        self.params = {} # Path params, filled later

async def get_session(request: Request):
    sid = request.cookies.get("session_id")
    header_sid = request.headers.get("X-Nexo-Session-Id")
    
    # logger.debug(f"get_session | CookieSID: {sid} | HeaderSID: {header_sid}")
    
    session = None
    if sid:
        session = Session.load(sid)
        if not session:
             pass # logger.debug(f"Cookie session {sid} invalid/expired.")

    # Fallback to header if cookie failed or was missing
    if not session and header_sid:
        # logger.debug(f"Trying header session: {header_sid}")
        session = Session.load(header_sid)
        if session:
            # logger.debug(f"Header session {header_sid} valid! Using it.")
            pass
    
    if not session:
        session = Session.new()
        logger.info(f"Created new session {session.sid} for IP {request.client.host}")
    
    return session

async def get_env(request: Request, session: Session = Depends(get_session)):
    try:
        # Create DB Connection/Cursor per request
        # Since we are in a threadpool (FastAPI default for def), we can use blocking calls
        # But Database.cursor() requires a connection.
        # We use the singleton connection for SQLite.
        
        # Transaction Management:
        # We want a fresh cursor.
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        uid = session.uid
        # logger.debug(f"Env Created | UID: {uid} | SID: {session.sid}")
        env = Environment(cr, uid=uid)
        
        try:
            yield env
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            # Release connection back to pool
            Database.release(conn)

            
    except Exception as e:
        logger.critical(f"get_env Dependency Failed: {e}", exc_info=True)
        raise e

# --- Legacy Route Adapter ---
# The tricky part: existing controllers expect (req, env) and return Response object.

async def dynamic_handler(request: Request, env: Environment = Depends(get_env), session: Session = Depends(get_session)):
    # 1. Match Route manually (since we are creating a catch-all or specific routes)
    # Actually, better strategy: Register specific routes in FastAPI based on ROUTES dict.
    pass

def register_legacy_routes():
    """
    Iterate over ROUTES (from core.http) and register them in FastAPI.
    """
    for route_path, info in ROUTES.items():
        # route_path might contain regex-like <int:id>, we need to convert to FastAPI format {id}
        # core.http logic: <int:id> -> regex
        # FastAPI: /path/{id}
        
        # Simplification: Convert <type:name> to {name}
        # Regex replacement
        fastapi_path = re.sub(r'<(?:\w+:)?(\w+)>', r'{\1}', route_path)
        
        func = info['func']
        auth_required = info['auth'] == 'user'
        print(f"Server Registering: {fastapi_path} | AuthRequired: {auth_required}")
        methods = ['GET', 'POST', 'PUT', 'DELETE']
        
        # Create a closure for the handler
        # We need to capture 'func' and 'auth_required'
        
        async def handler(
            request: Request, 
            env: Environment = Depends(get_env), 
            session: Session = Depends(get_session),
            # Fix Closure Capture: Bind current loop values
            func=func, 
            auth_required=auth_required
        ):
            print(f"Handler Hit: {request.url.path} | AuthReq: {auth_required} | UID: {session.uid}", flush=True)
            # 1. Auth Check
            if auth_required and not session.uid:
                print(f"Handler Denied 403: {request.url.path}")
                return JSONResponse({"error": "Access Denied"}, status_code=403)
            
            # 2. Body Parsing (if JSON)
            json_body = {}
            try:
                json_body = await request.json()
            except:
                pass
            
            # 3. Request Wrapper
            # We need to populate 'params' (path variables)
            # FastAPI passes them as kwargs to the handler usually.
            # But here we are using a generic handler.
            # We can extract them from request.path_params if we used generic route?
            # Or reliance on FastAPI to pass them?
            
            # Let's inspect request.path_params
            req_wrapper = RequestContext(request, session, json_body)
            req_wrapper.params = request.path_params
            
            # 4. Call Legacy Controller
            # Run in threadpool? FastAPI does this automatically if this wrapper is 'def',
            # BUT we defined it as 'async def' to use 'await request.json()'.
            # Wait, if we use 'async def', we block the loop if we call sync code?
            # YES.
            # We should probably define this as 'async def' but offload the sync call?
            # OR define as 'def' and use sync primitives? FastAPI doesn't support sync body read easily?
            # Actually, we can just call the sync func directly? No, 'func' is blocking.
            # If we are in 'async def', we MUST await blocking calls in run_in_executor.
            
            from starlette.concurrency import run_in_threadpool
            
            try:
                # Execute Controller
                response_obj = await run_in_threadpool(func, req_wrapper, env)
                
                # 5. Convert Response
                # response_obj is core.http.Response
                
                content = response_obj.body
                if isinstance(content, dict):
                    return JSONResponse(content, status_code=response_obj.status)
                
                # HTML/Text
                fast_response = FastAPIResponse(
                    content=str(content), 
                    status_code=response_obj.status,
                    media_type=response_obj.content_type
                )
                
                # Cookies
                # Handler set cookies in response_obj.cookies (SimpleCookie)
                # We need to transfer them
                if hasattr(response_obj, 'cookies'):
                    for morsel in response_obj.cookies.values():
                         fast_response.set_cookie(
                             key=morsel.key, 
                             value=morsel.value,
                             httponly=morsel['httponly'],
                             path=morsel['path'] or '/'
                         )

                # Session Cookie Persistence
                # Critical Fix: Always set cookie if the session in use is different from the one in request request
                # OR if it's a new session.
                
                req_sid = request.cookies.get("session_id")
                res_sid = session.sid
                
                if req_sid != res_sid:
                    print(f"DEBUG: Updating Session Cookie {req_sid} -> {res_sid}", flush=True)
                    fast_response.set_cookie('session_id', res_sid, path='/', httponly=True, samesite='Lax')
                
                return fast_response
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                return JSONResponse({"error": str(e)}, status_code=500)

        # Register the route
        # Using a distinct function name to avoid overwrites? FastAPI uses unique objects.
        # But for 'operation_id' unique names are good.
        handler.__name__ = f"handler_{func.__name__}_{hash(route_path)}"
        
        app.add_api_route(
            fastapi_path, 
            handler, 
            methods=methods,
            include_in_schema=False # Hide from Swagger for now as they are legacy
        )
        print(f"Registered Route: {fastapi_path}")

register_legacy_routes()

# --- Static Files ---
# Mount /addons
# Note: In real life we'd want /web/static, /sales/static etc.
# But for now, let's expose specific folders or a root addons folder
# User asked for '/web/static' support etc.
# core/http dispatch logic: /<module>/static/<file>
# We can't map this easily with StaticFiles unless we mount each module?
# Or we use a generic path handler for static?

from fastapi.staticfiles import StaticFiles

# Approach: Catch-all for /static/
# But URL is /module/static/file

@app.get("/{module}/static/{file_path:path}")
async def serve_static(module: str, file_path: str):
    # Security: Sanitization (FastAPI path params usually safe-ish, but check ..)
    if ".." in file_path:
        return Response("Forbidden", status_code=403)
    
    # Locate file in addons
    base_path = os.getcwd()
    full_path = os.path.join(base_path, 'addons', module, 'static', file_path)
    
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return FastAPIResponse(
            content=open(full_path, "rb").read(), 
            media_type="application/javascript" if file_path.endswith(".js") else 
                       "text/css" if file_path.endswith(".css") else None
        )
    return Response("Not Found", status_code=404)

# Web Client Root Redirect
@app.get("/")
def root():
    return HTMLResponse('<h1>Nexo ERP Enterprise Running 🚀</h1>')

if __name__ == "__main__":
    uvicorn.run("core.http_fastapi:app", host="0.0.0.0", port=8000, reload=True)
