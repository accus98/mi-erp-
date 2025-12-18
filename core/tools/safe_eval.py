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
        # Fix DoS: Limit execution time to 2 seconds.
        
        aeval = Interpreter(usersyms=context, minimal=False, max_time=2) 
        
        try:
            return aeval.eval(expr)
        except Exception as e:
            # If asteval fails (syntax or runtime), raise standard error
            # asteval usually captures errors in aeval.error
            error_msg = aeval.error if aeval.error else [str(e)]
            raise ValueError(f"Safe Eval Error on '{expr}': {error_msg}")
            
    else:
        # CRITICAL SECURITY FIX: RCE Prevention
        # We DO NOT fall back to eval() if asteval is missing.
        # The risk of sandbox escape is too high.
        raise ImportError("CRITICAL: 'asteval' library is missing. Safe execution is impossible. Please install it.")

