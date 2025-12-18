# API Package

def depends(*args):
    """
    Decorator that marks the dependencies of a compute method.
    Example:
        @depends('price', 'qty')
        def _compute_total(self): ...
    """
    def decorator(func):
        func._depends = args
        return func
    return decorator
