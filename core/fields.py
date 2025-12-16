import inspect

class Field:
    """
    Base class for all fields.
    """
    _type = None
    _sql_type = None

    def __init__(self, string=None, required=False, help=None, readonly=False, compute=None, store=True, default=None, translate=False, groups=None):
        self.string = string
        self.required = required
        self.help = help
        self.readonly = readonly
        self.name = None
        self.compute = compute
        self.store = store
        self.default = default
        self.translate = translate
        self.groups = groups
        
        if compute and not store:
            self.store = False
            self._sql_type = None 

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.name}>"

    def __get__(self, record, owner):
        if record is None: return self
        if not record.ids: return None
        
        record.ensure_one()
        id_val = record.ids[0]
        
        # Optimization: 'id' field is always available sync
        if self.name == 'id':
            return id_val
            
        key = (record._name, id_val, self.name)
        
        # Translation Cache Check
        lang = record.env.context.get('lang')
        if getattr(self, 'translate', False) and lang and lang != 'en_US':
             key_trans = (record._name, id_val, self.name, lang)
             if key_trans in record.env.cache:
                 return record.env.cache[key_trans]
             # Cannot fetch translation sync.
             raise RuntimeError(f"AsyncORM: Translation for field '{self.name}' not in cache. Use await record.read() with lang='{lang}' context.")

        if key in record.env.cache:
            return record.env.cache[key]
        
        # Computed Field - Cannot execute Sync
        if self.compute:
             raise RuntimeError(f"AsyncORM: Computed field '{self.name}' not in cache. Usage of sync access is forbidden. Call compute method or read().")

        # Stored Field - Cannot execute Sync
        raise RuntimeError(f"AsyncORM: Field '{self.name}' not in cache. Use await record.read(['{self.name}']) or await record.fetch(['{self.name}']).")
    
    def __set__(self, record, value):
        if record is None: return
        if not record.ids: return
        # record.ensure_one() # Write handles multiple records!
        if self.store and not self.compute: 
             record.write({self.name: value})
        
        # Update Cache always (for computed fields or write result)
        # Note: If write() is called, it might update cache too via invalidate/recompute?
        # But for non-stored computed fields, we MUST update cache here.
        for rid in record.ids:
             record.env.cache[(record._name, rid, self.name)] = value

class Char(Field):
    _type = 'char'
    _sql_type = 'VARCHAR'

class Text(Field):
    _type = 'text'
    _sql_type = 'TEXT'

class Selection(Field):
    _type = 'selection'
    _sql_type = 'VARCHAR'
    
    def __init__(self, selection, string=None, **kwargs):
        super().__init__(string=string, **kwargs)
        self.selection = selection


class Integer(Field):
    _type = 'integer'
    _sql_type = 'INTEGER'

class Boolean(Field):
    _type = 'boolean'
    _sql_type = 'BOOLEAN'

class Float(Field):
    _type = 'float'
    _sql_type = 'FLOAT'

class Datetime(Field):
    _type = 'datetime'
    _sql_type = 'TIMESTAMP'

class Date(Field):
    _type = 'date'
    _sql_type = 'DATE'

DateTime = Datetime

class Many2one(Field):
    _type = 'many2one'
    _sql_type = 'INTEGER' 

    def __init__(self, comodel_name, string=None, ondelete='set null', **kwargs):
        super().__init__(string=string, **kwargs)
        self.comodel_name = comodel_name
        self.ondelete = ondelete

    def __get__(self, record, owner):
        if record is None: return self
        # Super __get__ calls ensure_one
        val_id = super().__get__(record, owner)
        if not val_id:
             return record.env[self.comodel_name].browse([])
        return record.env[self.comodel_name].browse([val_id])

class One2many(Field):
    _type = 'one2many'
    _sql_type = None
    
    def __init__(self, comodel_name, inverse_name, string=None, **kwargs):
        super().__init__(string=string, **kwargs)
        self.comodel_name = comodel_name
        self.inverse_name = inverse_name
        self.store = False
    
    def __get__(self, record, owner):
        if record is None or not record.ids: return []
        record.ensure_one()
        return record.env[self.comodel_name].search([(self.inverse_name, '=', record.ids[0])])

class Many2many(Field):
    _type = 'many2many'
    _sql_type = None # No column in main table

    def __init__(self, comodel_name, string=None, relation=None, column1=None, column2=None, **kwargs):
        super().__init__(string=string, **kwargs)
        self.comodel_name = comodel_name
        self.relation = relation
        self.column1 = column1
        self.column2 = column2
        self.store = False
    
    def __get__(self, record, owner):
        if record is None or not record.ids: return []
        record.ensure_one()
        
        # Assumption: relation is populated by MetaModel (or user) before runtime usage.
        if not self.relation:
             return []

        query = f'SELECT "{self.column2}" FROM "{self.relation}" WHERE "{self.column1}" = %s'
        record.env.cr.execute(query, (record.ids[0],))
        res_ids = [r[0] for r in record.env.cr.fetchall()]
        
        return record.env[self.comodel_name].browse(res_ids)

class Binary(Field):
    _type = 'binary'
    _sql_type = None # Not stored in main table

    def __get__(self, record, owner):
        if record is None: return self
        if not record.ids: return None

        record.ensure_one()
        # Check cache
        key = (record._name, record.ids[0], self.name)
        if key in record.env.cache:
             return record.env.cache[key]
        
        # Fetch Attachment
        atts = record.env['ir.attachment'].search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.ids[0]),
             ('name', '=', self.name)
        ])
        val = atts[0].datas if atts else False
        record.env.cache[key] = val
        return val

    def __set__(self, record, value):
        # Trigger ORM write
        if record and record.ids:
            record.write({self.name: value})
