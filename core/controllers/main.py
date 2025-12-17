from core.http import route, Response
import inspect

@route('/', auth='public')
async def index(req, env):
    return Response("<h1>Nexo ERP Running</h1>")

@route('/web/login', auth='public')
async def login(req, env):
    # JSON: {login, password}
    params = req.json.get('params', {})
    login = params.get('login') or req.json.get('login')
    password = params.get('password') or req.json.get('password')
    
    print(f"LOGIN ATTEMPT: {login}", flush=True)
    
    # Use SUDO to check credentials (Public user cannot search res.users)
    from core.env import Environment
    sudo_env = Environment(env.cr, uid=1)
    # Prefetch user for sudo logic? not needed if checking by SQL?
    # UsersSudo._check_credentials likely does search/read.
    UsersSudo = sudo_env['res.users']
    
    uid = await UsersSudo._check_credentials(login, password)
    
    if uid:
        req.session.rotate() # Prevent Fixation
        req.session.uid = uid
        req.session.login = login
        req.session.save() # Persist
        return Response({'result': {'uid': uid, 'session_id': req.session.sid}})
    else:
        return Response({'error': 'Access Denied'}, status=401)

@route('/web/dataset/call_kw', auth='user')
async def call_kw(req, env):
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
    
    print(f"DEBUG_TRACE: call_kw ENTRY | Model: {model_name} | Method: {method_name} | UID: {env.uid}", flush=True)

    # 4. Execute
    try:
        # Transactional Wrapper
        # If any error occurs inside, rollback happens automatically via context manager.
        # But here we are already inside global handler transaction. A savepoint is useful for partial errors.
        # Using Async Savepoint logic? AsyncCursor wrapper should support it or we use raw conn.transaction(savepoint=True).
        # For simplicity, we rely on main transaction now.
        if True: # with env.cr.savepoint(): # TODO: implement async savepoint on Env or Cursor
            model = env[model_name]
            
            # Handle Instance Methods (read, write, unlink)
            # These methods expect 'self' to be a recordset, so we must instantiate it 
            # using the first argument (ids) from args.
            instance_methods = ['read', 'write', 'unlink', 'check_access_rights']
            # And many Odoo methods.
            
            # We assume instance method if args[0] is list of IDs? Or based on name?
            # Safer: Try to bind if first arg matches?
            # Standard Odoo call_kw logic:
            
            is_instance_call = method_name in instance_methods or (args and isinstance(args[0], list) and method_name not in ['search', 'search_count', 'create', 'search_read', 'name_search'])
            
            if is_instance_call and args and isinstance(args[0], list):
                ids = args[0]
                method_args = args[1:]
                record = model.browse(ids)
                method = getattr(record, method_name)
                result = method(*method_args, **kwargs)
            else:
                # Static methods or methods called on empty recordset (search, create, etc.)
                method = getattr(model, method_name)
                result = method(*args, **kwargs)
            
            if inspect.iscoroutine(result):
                result = await result

            if hasattr(result, 'ids'):
                 result = result.ids
            
            print(f"DEBUG_TRACE: call_kw EXIT | Result: {str(result)[:100]}...", flush=True)
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
async def destroy(req, env):
    req.session.uid = None
    req.session.save()
    return Response({'result': True})

@route('/web/session/check', auth='user')
async def check(req, env):
    return Response({'result': {'uid': req.session.uid, 'login': req.session.login}})
