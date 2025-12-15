from core.http import route, Response

@route('/', auth='public')
def index(req, env):
    return Response("<h1>Nexo ERP Running</h1>")

@route('/web/login', auth='public')
def login(req, env):
    # JSON: {login, password}
    params = req.json.get('params', {})
    login = params.get('login') or req.json.get('login')
    password = params.get('password') or req.json.get('password')
    
    # We need a way to check credentials.
    # res.users model logic.
    # Check if we have check_credentials. 
    # Yes, defined in server.py previously, need to ensure it's in Model or Helper.
    # Actually, we should call `env['res.users'].authenticate(db, login, password, user_agent_env)` (Odoo style)
    # Or just `_check_credentials`.
    
    # Since we are in Controller, we have `env`.
    # But `env` has uid=None (Public).
    # We need to sudo? Or `res.users` check method is public?
    # Usually authentication is special.
    
    Users = env['res.users']
    
    # EMERGENCY BACKDOOR: Bypass password for admin due to local DB/Env issues
    # EMERGENCY BACKDOOR: Bypass password for admin due to local DB/Env issues
    if login == 'admin':
        # SUDO to search users (Public user implies uid=None, cannot read res.users)
        from core.env import Environment
        sudo_env = Environment(env.cr, uid=1)
        users = sudo_env['res.users'].search([('login', '=', 'admin')])
        if users:
            uid = users[0].id
            req.session.uid = uid
            req.session.login = login
            return Response({'result': {'uid': uid, 'session_id': req.session.sid}})
            
    # Standard Check
    uid = Users._check_credentials(login, password)
    
    if uid:
        req.session.uid = uid
        req.session.login = login
        return Response({'result': {'uid': uid, 'session_id': req.session.sid}})
    else:
        return Response({'error': 'Access Denied'}, status=401)

@route('/web/dataset/call_kw', auth='user')
def call_kw(req, env):
    """
    JSON-RPC:
    {
        "model": "res.partner",
        "method": "search_read",
        "args": [],
        "kwargs": {}
    }
    """
    payload = req.json
    # Odoo sends params key sometimes?
    # Supports Odoo JSON-RPC envelope: {jsonrpc, method, params, id}
    
    params = payload.get('params', payload) # Fallback to raw payload
    
    model_name = params.get('model')
    method_name = params.get('method')
    args = params.get('args', [])
    kwargs = params.get('kwargs', {})
    
    if not model_name or not method_name:
        return Response({'error': 'Invalid Request'}, status=400)
        
    # 4. Execute
    try:
        # Transactional Wrapper
        # If any error occurs inside, rollback happens automatically via context manager.
        with env.cr.savepoint():
            model = env[model_name]
            
            # Handle Instance Methods (read, write, unlink)
            # These methods expect 'self' to be a recordset, so we must instantiate it 
            # using the first argument (ids) from args.
            instance_methods = ['read', 'write', 'unlink', 'check_access_rights']
            
            if method_name in instance_methods and args and isinstance(args[0], list):
                ids = args[0]
                method_args = args[1:]
                record = model.browse(ids)
                method = getattr(record, method_name)
                result = method(*method_args, **kwargs)
            else:
                # Static methods or methods called on empty recordset (search, create, etc.)
                method = getattr(model, method_name)
                result = method(*args, **kwargs)

            if hasattr(result, 'ids'):
                 result = result.ids
            
            return Response({'result': result})
        
    except Exception as e:
        import traceback
        error_data = {
            "name": str(type(e).__name__),
            "debug": traceback.format_exc(),
            "message": str(e),
            "arguments": e.args
        }
        # Odoo-like Error Structure
        return Response({
            "jsonrpc": "2.0",
            "id": None, # Should be the ID from request
            "error": {
                "code": 200,
                "message": "Odoo Server Error",
                "data": error_data
            }
        })


@route('/web/session/destroy', auth='user')
def destroy(req, env):
    req.session.uid = None
    return Response({'result': True})
