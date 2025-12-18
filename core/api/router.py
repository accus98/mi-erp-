from fastapi import APIRouter, Depends, HTTPException, Request, Response
from core.db_async import AsyncDatabase
from core.env import Environment
from core.api.schema import get_pydantic_model, GenericResponse, LoginRequest, CallKwRequest
from core.session import Session, get_session
from typing import List, Any
from pydantic import ValidationError
import logging
import inspect

api_router = APIRouter(prefix="/api")

# Dependency to get Async Env
async def get_env(session: Session = Depends(get_session)):
    uid = session.uid
    context = session.context
    
    async with AsyncDatabase.acquire() as cr:
         if uid:
             await cr.execute(f"SET LOCAL app.current_uid = '{uid}'")
         
         env = Environment(cr, uid=uid, context=context)
         if uid:
             await env.prefetch_user()
         yield env

@api_router.post("/call", response_model=GenericResponse)
async def call(request: CallKwRequest, env: Environment = Depends(get_env)):
    """
    Generic execution endpoint.
    JSON: {model, method, args, kwargs}
    """
    uid = env.uid
    model_name = request.model
    method_name = request.method
    args = request.args
    kwargs = request.kwargs
    
    # print(f"DEBUG API CALL: {model_name}.{method_name} as {uid}")
    
    # Validation
    if not env.registry.get(model_name):
         raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
         
    Model = env[model_name]
    
    try:
         # Handle Instance Methods (args[0] is list of IDs)
         instance_methods = ['read', 'write', 'unlink', 'check_access_rights', 'name_get']
         is_instance_call = method_name in instance_methods or (args and isinstance(args[0], list) and method_name not in ['search', 'search_count', 'create', 'search_read', 'name_search'])
         
         if is_instance_call and args and isinstance(args[0], list):
             ids = args[0]
             method_args = args[1:]
             record = Model.browse(ids)
             method = getattr(record, method_name)
             result = method(*method_args, **kwargs)
         else:
             method = getattr(Model, method_name)
             result = method(*args, **kwargs)
         
         if inspect.iscoroutine(result):
             result = await result

         if hasattr(result, 'ids'):
              result = result.ids
              
         return GenericResponse(success=True, data=result)
         
    except Exception as e:
         import traceback
         traceback.print_exc()
         return GenericResponse(success=False, message=str(e))

@api_router.post("/login", response_model=GenericResponse)
async def login(request: LoginRequest, session: Session = Depends(get_session)):
    # 1. Create Sudo Env for Auth Check
    async with AsyncDatabase.acquire() as cr:
         sudo_env = Environment(cr, uid=1)
         Users = sudo_env['res.users']
         
         # 2. Check Credentials
         uid = await Users._check_credentials(request.login, request.password)
         
         if uid:
             session.rotate()
             session.uid = uid
             session.login = request.login
             session.save()
             return GenericResponse(success=True, data={'uid': uid, 'session_id': session.sid})
         else:
             # return 401? Or success=False?
             # GenericResponse suggests success=False logic usually?
             # But 401 is more RESTful.
             # Legacy main.py returns 401.
             raise HTTPException(status_code=401, detail="Access Denied")

@api_router.get("/{model}", response_model=GenericResponse)
async def list_records(model: str, env: Environment = Depends(get_env)):
    if not env.registry.get(model):
        raise HTTPException(status_code=404, detail="Model not found")
        
    Model = env[model]
    records = await Model.search([])
    data = await records.read()
    
    return GenericResponse(success=True, data=data)

@api_router.get("/{model}/{id}", response_model=GenericResponse)
async def read_record(model: str, id: int, env: Environment = Depends(get_env)):
    if not env.registry.get(model):
        raise HTTPException(status_code=404, detail="Model not found")
        
    Model = env[model]
    records = await Model.search([('id', '=', id)])
    if not records:
         raise HTTPException(status_code=404, detail="Record not found")
         
    data = await records.read()
    return GenericResponse(success=True, data=data[0])

@api_router.post("/{model}", response_model=GenericResponse)
async def create_record(model: str, payload: dict, env: Environment = Depends(get_env)):
    if not env.registry.get(model):
        raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        PayloadModel = get_pydantic_model(env[model], 'create')
        validated = PayloadModel(**payload)
        data = validated.dict(exclude_unset=True)
        
        Model = env[model]
        new_record = await Model.create(data)
        return GenericResponse(success=True, data={'id': new_record.id})
    except GenericResponse as e:
        # Pydantic validation error if we imported it? No, explicit check below
        raise e
    except ValidationError as e:
         raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        return GenericResponse(success=False, data=None, message=str(e))

@api_router.put("/{model}/{id}", response_model=GenericResponse)
async def update_record(model: str, id: int, payload: dict, env: Environment = Depends(get_env)):
    if not env.registry.get(model):
        raise HTTPException(status_code=404, detail="Model not found")
        
    Model = env[model]
    records = await Model.search([('id', '=', id)])
    if not records:
         raise HTTPException(status_code=404, detail="Record not found")
         
    try:
        PayloadModel = get_pydantic_model(env[model], 'write')
        validated = PayloadModel(**payload)
        data = validated.dict(exclude_unset=True)
        
        await records.write(data)
        return GenericResponse(success=True, data={'id': id})
    except ValidationError as e:
         raise HTTPException(status_code=422, detail=e.errors())
    except Exception as e:
        return GenericResponse(success=False, data=None, message=str(e))

@api_router.delete("/{model}/{id}", response_model=GenericResponse)
async def delete_record(model: str, id: int, env: Environment = Depends(get_env)):
    if not env.registry.get(model):
        raise HTTPException(status_code=404, detail="Model not found")
        
    Model = env[model]
    records = await Model.search([('id', '=', id)])
    if not records:
         raise HTTPException(status_code=404, detail="Record not found")
         
    try:
        await records.unlink()
        return GenericResponse(success=True, data={'id': id})
    except Exception as e:
        return GenericResponse(success=False, data=None, message=str(e))
