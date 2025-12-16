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

    @classmethod
    def __contains__(cls, item):
        return item in cls._models

    @property
    @classmethod
    def models(cls):
        return cls._models

    @classmethod
    async def setup_models(cls, cr):
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
        await IrModel._auto_init(cr)
        await IrFields._auto_init(cr)
        
        # 2. Sync Loop
        env = Environment(cr, uid=1) 
        # Using uid=1 (SysAdmin)
        
        for name, model_cls in cls._models.items():
            print(f"Init SQL for {name}")
            # Ensure Table Exists for all models
            await model_cls._auto_init(cr)
            
            # --- Sync ir.model ---
            # Search if exists
            existing = await env['ir.model'].search([('model', '=', name)])
            if not existing:
                await env['ir.model'].create({
                    'name': model_cls._description or name,
                    'model': name,
                    'transient': False # TODO: Detect transient
                })
                # Commit or keep in transaction? Keep in txn.
                # Get ID via search again or create returns record (Async create returns RecordSet)
                # But create returns proxy.
                model_record_set = await env['ir.model'].search([('model', '=', name)], limit=1)
                model_record = model_record_set[0]
            else:
                model_record = existing[0]

            # --- Sync ir.model.fields ---
            for field_name, field_obj in model_cls._fields.items():
                existing_field = await env['ir.model.fields'].search([
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
                    f_rec = await env['ir.model.fields'].create(vals)
                else:
                    # Optional: Update if changed
                    f_rec = existing_field[0]
                    # Update basic attrs?
                    # await f_rec.write(vals) 
                    pass
                
                # Sync Groups
                if getattr(field_obj, 'groups', None):
                    group_names = [g.strip() for g in field_obj.groups.split(',')]
                    # Resolve Groups (By Name for now)
                    # TODO: Support XML ID
                    group_ids = []
                    for g_name in group_names:
                        gs = await env['res.groups'].search([('name', '=', g_name)])
                        if gs:
                            group_ids.append(gs[0].id)
                    
                    if group_ids:
                        await f_rec.write({'groups_ids': group_ids}) 
        
        # cr.connection.commit() # Handled by Caller
        print("Model Sync Complete.")
