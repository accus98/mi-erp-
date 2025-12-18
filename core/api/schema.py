from pydantic import BaseModel, Field, create_model
from typing import List, Any, Optional, Dict, Union, Tuple

# Response Model
class GenericResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None

# Dynamic Pydantic Model Generator
def get_pydantic_model(model_cls, action='create'):
    """
    Creates a Pydantic model dynamically based on ORM model fields.
    """
    fields_def = {}
    
    # Iterate ORM fields
    for name, field in model_cls._fields.items():
        if name in ('id', 'create_date', 'write_date', 'create_uid', 'write_uid'):
            continue
            
        # Type Mapping
        py_type = str
        if field._type in ('integer', 'many2one'):
            py_type = int
        elif field._type == 'float':
            py_type = float
        elif field._type == 'boolean':
            py_type = bool
        elif field._type in ('one2many', 'many2many'):
            py_type = List[int] # List of IDs for writes
            
        # Required? 
        # For 'create', required=True fields are required.
        # For 'write', all optional (PATCH).
        is_required = field.required and action == 'create'
        
        if is_required:
             fields_def[name] = (py_type, ...)
        else:
             fields_def[name] = (Optional[py_type], None)
             
    name = f"{model_cls._name}_{action}"
    return create_model(name, **fields_def)


# Auth
class LoginRequest(BaseModel):
    login: str
    password: str

# Generic CRUD
class SearchRequest(BaseModel):
    domain: List[Any] = []
    offset: int = 0
    limit: Optional[int] = None
    order: Optional[str] = None

class SearchReadRequest(SearchRequest):
    fields: Optional[List[str]] = None

class WriteRequest(BaseModel):
    vals: Dict[str, Any]

class CreateRequest(BaseModel):
    vals: Union[Dict[str, Any], List[Dict[str, Any]]]

class CallKwRequest(BaseModel):
    model: str
    method: str
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}

