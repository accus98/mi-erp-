from .registry import Registry

class Environment:
    """
    The environment stores the context of the current transaction.
    It encapsulates the database cursor, the user ID, the context, and the cache.
    """
    def __init__(self, cr, uid, context=None):
        self.cr = cr
        self.uid = uid
        self.context = context or {}
        # Cache structure: {(model_name, id, field_name): value}
        self.cache = {}
        self._model_cache = {} # Cache for model classes/instances

    def __getitem__(self, model_name):
        """
        env['res.partner'] returns an empty RecordSet for that model.
        """
        return self.get(model_name)

    def get(self, model_name):
        model_cls = Registry.get(model_name)
        if not model_cls:
            raise KeyError(f"Model {model_name} not found in Registry.")
        
        # Return an instance of the model bound to this environment
        # The Model class (RecordSet) constructor expects (env, ids)
        return model_cls(self, ())

    @property
    def user(self):
        """Returns the RecordSet of the current user."""
        return self.get('res.users').browse([self.uid])
