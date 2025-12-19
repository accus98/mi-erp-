
import json
import re
from http.cookies import SimpleCookie
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


class Response:
    """
    Standard Response Object used by Controllers.
    Adapters convert this to framework-specific responses (e.g. FastAPI).
    """
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
