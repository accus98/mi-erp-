from core.db import Database

class Registry:
    """
    The Model Registry (Singleton).
    """
    _models = {}

    @classmethod
    def register(cls, name, model_cls):
        cls._models[name] = model_cls

    @classmethod
    def get(cls, name):
        return cls._models.get(name)

    @classmethod
    def keys(cls):
        return cls._models.keys()

    @property
    @classmethod
    def models(cls):
        return cls._models

    @classmethod
    def setup_models(cls, cr):
        """
        Synchronize Python models with Database (ir.model, ir.model.fields).
        """
        from core.env import Environment
        print("Syncing models to database...")
        # 1. Ensure ir.model and ir.model.fields tables exist first
        # We need to manually init them because they are in the registry but
        # might depend on themselves.
        IrModel = cls.get('ir.model')
        IrFields = cls.get('ir.model.fields')
        
        if not IrModel or not IrFields:
            print("Warning: Introspection models not loaded.")
            return

        # Explicitly init basic tables for these 2 essential models
        IrModel._auto_init(cr)
        IrFields._auto_init(cr)
        
        # 2. Sync Loop
        env = Environment(cr, uid=1) 
        # Using uid=1 (SysAdmin)
        
        for name, model_cls in cls._models.items():
            print(f"Init SQL for {name}")
            # Ensure Table Exists for all models
            model_cls._auto_init(cr)
            
            # --- Sync ir.model ---
            # Search if exists
            existing = env['ir.model'].search([('model', '=', name)])
            if not existing:
                env['ir.model'].create({
                    'name': model_cls._description or name,
                    'model': name,
                    'transient': False # TODO: Detect transient
                })
                # Commit or keep in transaction? Keep in txn.
                # Get ID via search again or create returns record
                model_record = env['ir.model'].search([('model', '=', name)])[0] # Lazy way
            else:
                model_record = existing[0]

            # --- Sync ir.model.fields ---
            for field_name, field_obj in model_cls._fields.items():
                existing_field = env['ir.model.fields'].search([
                    ('model_id', '=', model_record.id),
                    ('name', '=', field_name)
                ])
                
                vals = {
                    'model_id': model_record.id,
                    'name': field_name,
                    'ttype': field_obj._type or 'unknown',
                    'string': field_obj.string or field_name,
                    'required': field_obj.required,
                    'readonly': field_obj.readonly,
                    'relation': getattr(field_obj, 'comodel_name', None)
                }
                
                if not existing_field:
                    env['ir.model.fields'].create(vals)
                else:
                    # Optional: Update if changed
                    pass 
        
        cr.connection.commit()
        print("Model Sync Complete.")
