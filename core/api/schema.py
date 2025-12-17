from pydantic import BaseModel, create_model, Field as PydanticField
from typing import Any, List, Optional, Union, Dict
from core.fields import Char, Integer, Float, Boolean, Many2one, One2many, Many2many, Selection, Text, Binary, Date, Datetime

class SchemaFactory:
    """
    Generates Pydantic Models dynamically from Odoo Models.
    Used for API validation and automatic documentation (OpenAPI).
    """
    
    _schema_cache = {}

    @classmethod
    def get_create_schema(cls, env, model_name: str) -> BaseModel:
        cache_key = (model_name, 'create')
        if cache_key in cls._schema_cache:
            return cls._schema_cache[cache_key]
            
        model = env[model_name]
        fields_def = {}
        
        for name, field in model._fields.items():
            if name in ('id', 'create_date', 'write_date', 'create_uid', 'write_uid'):
                continue
            
            py_type = cls._get_python_type(field)
            
            # Create: Required fields are required. Others optional.
            if field.required:
                fields_def[name] = (py_type, ...) # Ellipsis means required
            else:
                fields_def[name] = (Optional[py_type], None)
                
        pydantic_model = create_model(f"{model_name}Create", **fields_def)
        cls._schema_cache[cache_key] = pydantic_model
        return pydantic_model

    @classmethod
    def get_write_schema(cls, env, model_name: str) -> BaseModel:
        cache_key = (model_name, 'write')
        if cache_key in cls._schema_cache:
            return cls._schema_cache[cache_key]
            
        model = env[model_name]
        fields_def = {}
        
        for name, field in model._fields.items():
            if name in ('id', 'create_date', 'write_date', 'create_uid', 'write_uid'):
                continue
                
            py_type = cls._get_python_type(field)
            
            # Write: All fields are optional (partial update)
            fields_def[name] = (Optional[py_type], None)

        pydantic_model = create_model(f"{model_name}Write", **fields_def)
        cls._schema_cache[cache_key] = pydantic_model
        return pydantic_model
        
    @classmethod
    def _get_python_type(cls, field):
        if isinstance(field, (Integer, Many2one)):
            return int
        elif isinstance(field, Float):
            return float
        elif isinstance(field, Boolean):
            return bool
        elif isinstance(field, (Char, Text, Selection, Date, Datetime)):
            return str
        elif isinstance(field, (One2many, Many2many)):
            # Accepts List of IDs or List of Command Tuples
            # Simple validation: List[Any] for now to allow [1, 2] AND [(6, 0, [1])]
            return List[Any] 
        elif isinstance(field, Binary):
            return str # Base64 string
        return Any

class GenericResponse(BaseModel):
    success: bool
    data: Any
    message: Optional[str] = None
