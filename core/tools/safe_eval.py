import ast
import datetime
import time

def safe_eval(expr, globals_dict=None, locals_dict=None):
    """
    Safely evaluate an expression string using a restricted environment.
    Prevents access to unsafe builtins like __import__, open, etc.
    
    WARNING: This uses 'eval()'. While heavily restricted, it is not a perfect sandbox.
    For High-Security environments, migrate to 'asteval' or a strict parser.
    """
    if globals_dict is None:
        globals_dict = {}
    if locals_dict is None:
        locals_dict = {}

    # whitelist of safe functions/modules
    safe_globals = {
        '__builtins__': {}, # CRITICAL: Remove builtins
        'datetime': datetime,
        'time': time,
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'bool': bool,
        'list': list,
        'dict': dict,
        'tuple': tuple,
        'set': set,
        'True': True,
        'False': False,
        'None': None,
    }
    
    # Merge user globals but override critical ones
    ctx = safe_globals.copy()
    ctx.update(globals_dict)
    ctx['__builtins__'] = {} # Enforce emptiness again just in case
    
    # Simple check for double underscores (often used in exploits)
    if '__' in expr:
        # Check if it's strictly necessary? Odoo domains use fields like parent_id.name?
        # No, fields are strings "parent_id.name".
        # Expr might be "uid == 1".
        # Exploit: "().__class__.__bases__..."
        # If we block "__", we block magic methods access.
        # Exception: maybe some valid variables uses __? unlikely in domains.
        raise ValueError("Security Error: Double underscores not allowed in domains.")
        
    try:
        # Use eval with restricted scope
        return eval(expr, ctx, locals_dict)
    except Exception as e:
        raise ValueError(f"Safe Eval Error on '{expr}': {e}")
