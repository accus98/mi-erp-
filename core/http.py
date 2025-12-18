# WARNING: THIS MODULE IS LEGACY/BLOCKING.
# It contains synchronous I/O (File Sessions).
# FastAPI uses core/session.py instead.
# DO NOT USE core.http.Session in async code.

import json
import uuid
import threading
import re
import os
import mimetypes
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlparse
from datetime import datetime, date

def json_default(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# Global Routing Map
# Path -> {handler, auth, regex, variables}
ROUTES = {}

def route(route_path, auth='user'):
    """
    Decorator to register a route.
    Supports variables like /path/<model>/<int:id>
    """
    def decorator(func):
        # Parse route_path to regex
        # Supports <name>, <int:name>, <string:name>
        
        def repl(match):
            type_ = match.group(1)
            name = match.group(2)
            if type_ == 'int':
                return f'(?P<{name}>\\d+)'
            else:
                return f'(?P<{name}>[^/]+)'
        
        # Regex to find <(type:)?name>
        # We need to match <int:id> or <id>
        # Pattern: <(?:(\w+):)?(\w+)>
        
        pattern = re.sub(r'<(?:\b(int|string):)?(\w+)>', repl, route_path)
        
        regex = re.compile(f"^{pattern}$")
        
        ROUTES[route_path] = {
            'func': func,
            'auth': auth,
            'regex': regex,
            'is_dynamic': '<' in route_path
        }
        return func
    return decorator


import secrets

class Session:
    # File-based Persistence
    SESSION_DIR = 'sessions'

    def __init__(self, sid):
        self.sid = sid
        self.uid = None
        self.login = None
        self.context = {}
        self.csrf_token = secrets.token_urlsafe(32)
        self._dirty = False

    @classmethod
    def _get_path(cls, sid):
        if not os.path.exists(cls.SESSION_DIR):
            os.makedirs(cls.SESSION_DIR, exist_ok=True)
        # Sanitize SID to prevent traversal
        safe_sid = os.path.basename(sid)
        return os.path.join(cls.SESSION_DIR, f"{safe_sid}.json")

    @classmethod
    def new(cls):
        sid = secrets.token_urlsafe(32)
        sess = cls(sid)
        sess.save()
        return sess

    @classmethod
    def load(cls, sid):
        path = cls._get_path(sid)
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                sess = cls(sid)
                sess.uid = data.get('uid')
                sess.login = data.get('login')
                sess.context = data.get('context', {})
                # Restore or rotate CSRF
                sess.csrf_token = data.get('csrf_token', sess.csrf_token)
                return sess
            except:
                return None
        return None

    def save(self):
        path = self._get_path(self.sid)
        data = {
            'uid': self.uid,
            'login': self.login,
            'context': self.context,
            'csrf_token': self.csrf_token
        }
        with open(path, 'w') as f:
            json.dump(data, f)
        self._dirty = False

class Request:
    def __init__(self, handler):
        self._handler = handler # http.server.BaseHTTPRequestHandler
        self.path = handler.path
        self.headers = handler.headers
        self.command = handler.command
        
        # Parse Cookies
        self.cookies = SimpleCookie(self.headers.get('Cookie'))
        self.sid = None
        if 'session_id' in self.cookies:
            self.sid = self.cookies['session_id'].value
            
        # Parse Query
        parsed = urlparse(self.path)
        self.query_params = parse_qs(parsed.query) # returns {key: [val]}
        self.path_clean = parsed.path
        
        # JSON Body
        self.json = {}
        if 'Content-Length' in self.headers:
            length = int(self.headers['Content-Length'])
            if length > 0:
                body = self._handler.rfile.read(length)
                try:
                    self.json = json.loads(body.decode('utf-8'))
                except:
                    pass
        
        # Session lazy load
        self._session = None
        self.params = {} # Path variables

    @property
    def session(self):
        if not self._session:
            if self.sid:
                self._session = Session.load(self.sid)
            if not self._session:
                self._session = Session.new()
                self.sid = self._session.sid
        return self._session

    @property
    def env(self):
        pass

class Response:
    def __init__(self, body=None, status=200, headers=None, content_type='text/html'):
        self.body = body if body is not None else ""
        self.status = status
        self.headers = headers or {}
        self.cookies = SimpleCookie()
        self.content_type = content_type

    def set_cookie(self, key, value, httponly=True, path='/'):
        self.cookies[key] = value
        self.cookies[key]['path'] = path
        if httponly:
            self.cookies[key]['httponly'] = True

    def render(self):
        if isinstance(self.body, dict) or isinstance(self.body, list):
            self.body = json.dumps(self.body, default=json_default)
            self.content_type = 'application/json'
        
        if isinstance(self.body, bytes):
            return self.body
            
        if isinstance(self.body, str):
            data = self.body.encode('utf-8')
        else:
            data = str(self.body).encode('utf-8')
            
        return data

def dispatch(handler):
    """
    Main dispatch logic.
    handler: http.server.BaseHTTPRequestHandler
    """
    req = Request(handler)
    
    # 0. Static Middleware
    # Pattern: /<module>/static/<file_path>
    # Regex: ^/([^/]+)/static/(.+)$
    static_match = re.match(r'^/([^/]+)/static/(.+)$', req.path_clean)
    if static_match:
        mod_name = static_match.group(1)
        file_path = static_match.group(2)
        
        # Check integrity (no traverse up)
        base_path = os.path.join(os.getcwd(), 'addons', mod_name, 'static')
        full_path = os.path.join(base_path, file_path)
        
        # Security: Path Traversal Fix
        # 1. Resolve to absolute path
        abs_base = os.path.abspath(base_path)
        abs_target = os.path.abspath(full_path)
        
        # 2. Verify strict containment
        if not abs_target.startswith(abs_base):
             print(f"SECURITY ALERT: Path Traversal attempt blocked: {file_path}")
             handler.send_error(403, "Forbidden")
             return
        
        if os.path.exists(full_path) and os.path.isfile(full_path):
            try:
                mime_type, _ = mimetypes.guess_type(full_path)
                mime_type = mime_type or 'application/octet-stream'
                
                with open(full_path, 'rb') as f:
                    content = f.read()
                    
                handler.send_response(200)
                handler.send_header('Content-Type', mime_type)
                handler.send_header('Content-Length', str(len(content)))
                handler.end_headers()
                handler.wfile.write(content)
                return
            except Exception as e:
                print(f"Static Serve Error: {e}")
                handler.send_error(500)
                return
        else:
             handler.send_error(404, "Static File Not Found")
             return

    # 1. Match Route
    route_info = ROUTES.get(req.path_clean)
    
    # If not exact match, try dynamic
    if not route_info:
        for path, info in ROUTES.items():
            if info['is_dynamic']:
                m = info['regex'].match(req.path_clean)
                if m:
                    route_info = info
                    req.params = m.groupdict()
                    break
    
    if not route_info:
        handler.send_error(404, "Not Found")
        return

    func = route_info['func']
    auth = route_info['auth']
    
    # 2. Auth Check
    if auth == 'user':
        if not req.session.uid:
            # Check JSON-RPC vs HTML request?
            # Basic Login Redirect or 403
            handler.send_error(403, "Forbidden: Login Required")
            return

    # 2.5 CSRF Check
    if req.command in ('POST', 'PUT', 'DELETE', 'PATCH'):
        # Exemptions
        if req.path_clean not in ['/web/login', '/web/session/destroy', '/web/session/check']:
            token = req.headers.get('X-CSRF-Token')
            if not token or token != req.session.csrf_token:
                print(f"SECURITY ALERT: CSRF Mismatch in Legacy Dispatch: {req.path_clean}")
                handler.send_error(403, "Forbidden: CSRF Token Invalid")
                return
            
    # 3. DB Context
    from core.db import Database
    from core.registry import Registry
    from core.env import Environment

    conn = Database.connect()
    try:
        cr = Database.cursor(conn)
        
        uid = req.session.uid
        env = Environment(cr, uid=uid)
        
        # 4. Call Controller
        resp = func(req, env)
        
        # 5. Send Response
        if isinstance(resp, Response):
            # Write Status
            handler.send_response(resp.status)
            
            # Write Headers
            handler.send_header('Content-Type', resp.content_type)
            for k, v in resp.headers.items():
                handler.send_header(k, v)
            
            # Write Cookies
            if req._session: # If session accessed/created, ensure cookie set
                 resp.set_cookie('session_id', req.session.sid)
            
            for morsel in resp.cookies.values():
                handler.send_header('Set-Cookie', morsel.OutputString())
            
            # Render Body (might be bytes)
            body_bytes = resp.render()
            
            if 'Content-Length' not in resp.headers:
                 handler.send_header('Content-Length', str(len(body_bytes)))
            
            handler.end_headers()
            handler.wfile.write(body_bytes)
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Dispatch Error: {e}")
        import traceback
        traceback.print_exc()
        handler.send_error(500, f"Internal Server Error: {e}")
    finally:
        Database.release(conn)
