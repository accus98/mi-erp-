
from pydantic import BaseModel, create_model
from typing import Any, Dict, List, Optional
from core.fields import Char, Integer, Float, Boolean, Text, Selection, Many2one, One2many, Many2many, Date, Datetime

# Cache generated models to avoid recreation
_model_cache = {}

def get_pydantic_model(env_model, mode='read'):
    """
    Dynamically creates a Pydantic Model from an ORM Model instance or class.
    mode: 'read' (all fields) or 'write' (only writable fields, no IDs)
    """
    model_name = env_model._name
    cache_key = f"{model_name}_{mode}"
    
    if cache_key in _model_cache:
        return _model_cache[cache_key]
        
    fields_def = {}
    
    # Iterate ORM fields
    for fname, field in env_model._fields.items():
        if fname == 'id' and mode == 'write':
            continue
            
        pydantic_type = str
        default = None
        
        # Mapping Types
        if isinstance(field, Integer):
            pydantic_type = int
        elif isinstance(field, Float):
            pydantic_type = float
        elif isinstance(field, Boolean):
            pydantic_type = bool
        elif isinstance(field, (Char, Text, Selection)):
            pydantic_type = str
        elif isinstance(field, (Date, Datetime)):
            pydantic_type = str # For now simple string ISO
        elif isinstance(field, Many2one):
             # For write: accepts ID (int)
             # For read: returns ID (int) or tuple (id, name) depending on context?
             # Let's standardize on ID for REST API simplicity for now.
             pydantic_type = Optional[int]
        elif isinstance(field, (One2many, Many2many)):
             # List of IDs 
             pydantic_type = List[int]
             default = []
             
        # Optionality
        if not field.required:
             pydantic_type = Optional[pydantic_type]
             
        fields_def[fname] = (pydantic_type, default)
    
    # Create the class
    pydantic_model = create_model(
        f"{model_name.replace('.', '_')}_{mode}",
        **fields_def
    )
    
    _model_cache[cache_key] = pydantic_model
    return pydantic_model

class GenericResponse(BaseModel):
    success: bool
    data: Any
    message: Optional[str] = None
