
from fastapi import APIRouter, Depends, HTTPException, Request
from core.db_async import AsyncDatabase
from core.env import Environment
from core.api.schema import get_pydantic_model, GenericResponse
from typing import List, Any
import logging

api_router = APIRouter(prefix="/api")

# Dependency to get Async Env
# Replicates core/http_fastapi.py logic but cleaner for API
async def get_env(request: Request):
    # Retrieve session from middleware/dependency
    # For now, let's assume session is attached to request or passed via token header
    # Simple Mock for MVP:
    uid = 1 # Admin default
    
    # We need to acquire a connection
    # FastAPI dependency with yield is perfect for resource management
    async with AsyncDatabase.acquire() as cr:
         env = Environment(cr, uid=uid)
         await env.prefetch_user()
         yield env

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
    
    # TODO: Validate payload with get_pydantic_model(env[model], 'write')
    # For now, simplistic generic dict pass-through to ORM
    
    try:
        Model = env[model]
        new_record = await Model.create(payload)
        return GenericResponse(success=True, data={'id': new_record.id})
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
        await records.write(payload)
        return GenericResponse(success=True, data={'id': id})
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
