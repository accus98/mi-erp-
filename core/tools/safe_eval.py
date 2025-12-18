import ast
import datetime
import time

try:
    from asteval import Interpreter
except ImportError:
    Interpreter = None
    print("WARNING: 'asteval' not found. Falling back to unsafe eval(). Please install 'asteval'.")

def safe_eval(expr, globals_dict=None, locals_dict=None):
    """
    Safely evaluate an expression using 'asteval'.
    This provides a much stronger sandbox than restricted eval().
    """
    if globals_dict is None:
        globals_dict = {}
    if locals_dict is None:
        locals_dict = {}

    # whitelist of safe functions/modules (asteval has its own defaults, we extend/restrict)
    # asteval by default includes math, time, etc.
    
    # We want to support: datetime, time, str, int, float, bool, list, dict, set, tuple, len, True, False, None
    # Plus variables from globals_dict/locals_dict
    
    context = {}
    if globals_dict: context.update(globals_dict)
    if locals_dict: context.update(locals_dict)
    
    # Context overrides
    context['datetime'] = datetime
    context['time'] = time
    
    if Interpreter:
        # Create Interpreter
        # minimal=True removes most builtins/math to be stricter? 
        # But Odoo domains often use len(), etc.
        # We rely on asteval's safe defaults (no open, no import).
        
        aeval = Interpreter(usersyms=context, minimal=False) 
        
        try:
            return aeval.eval(expr)
        except Exception as e:
            # If asteval fails (syntax or runtime), raise standard error
            # asteval usually captures errors in aeval.error
            error_msg = aeval.error if aeval.error else [str(e)]
            raise ValueError(f"Safe Eval Error on '{expr}': {error_msg}")
            
    else:
        # FALLBACK (Legacy/Unsafe) - Just in case install fails temporarily
        # Warning already printed globally. Not repeating per call to avoid spam.
        
        safe_globals = {
            '__builtins__': {}, 
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
        
        ctx = safe_globals.copy()
        ctx.update(globals_dict)
        if locals_dict: ctx.update(locals_dict)
        ctx['__builtins__'] = {} 
        
        if '__' in expr:
            raise ValueError("Security Error: Double underscores not allowed in domains.")
            
        try:
            return eval(expr, ctx)
        except Exception as e:
            raise ValueError(f"Safe Eval (Legacy) Error on '{expr}': {e}")
