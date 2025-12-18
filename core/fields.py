import inspect
from typing import TypeVar, Generic, Optional, TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from .orm import Model

T = TypeVar('T')

class Field(Generic[T]):
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

    def __get__(self, record, owner) -> T:
        if record is None: return self # type: ignore
        if not record.ids: return None # type: ignore
        
        record.ensure_one()
        id_val = record.ids[0]
        
        # Optimization: 'id' field is always available sync
        if self.name == 'id':
            return id_val # type: ignore
            
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
        raise RuntimeError(f"AsyncORM: Field '{self.name}' not in cache. Use await record.ensure('{self.name}').")
    
    def __set__(self, record, value):
        if record is None: return
        if not record.ids: return
        
        # 1. Update Cache
        for rid in record.ids:
             record.env.cache[(record._name, rid, self.name)] = value
             
        # 2. Trigger Modified (Sync)
        record._modified([self.name])
        
        # 3. Buffer Write if Stored
        if self.store: 
             for rid in record.ids:
                 key = (record._name, rid)
                 if key not in record.env.pending_writes:
                     record.env.pending_writes[key] = {}
                 record.env.pending_writes[key][self.name] = value

class Char(Field[str]):
    _type = 'char'
    _sql_type = 'VARCHAR'

class Text(Field[str]):
    _type = 'text'
    _sql_type = 'TEXT'

class Selection(Field[str]):
    _type = 'selection'
    _sql_type = 'VARCHAR'
    
    def __init__(self, selection, string=None, **kwargs):
        super().__init__(string=string, **kwargs)
        self.selection = selection


class Integer(Field[int]):
    _type = 'integer'
    _sql_type = 'INTEGER'

class Boolean(Field[bool]):
    _type = 'boolean'
    _sql_type = 'BOOLEAN'

class Float(Field[float]):
    _type = 'float'
    _sql_type = 'FLOAT'

class Datetime(Field[Any]): # Helper for datetime
    _type = 'datetime'
    _sql_type = 'TIMESTAMP'

class Date(Field[Any]):
    _type = 'date'
    _sql_type = 'DATE'

DateTime = Datetime

class Many2one(Field['Model']):
    _type = 'many2one'
    _sql_type = 'INTEGER' 

    def __init__(self, comodel_name, string=None, ondelete='set null', **kwargs):
        super().__init__(string=string, **kwargs)
        self.comodel_name = comodel_name
        self.ondelete = ondelete

    def __get__(self, record, owner) -> 'Model':
        if record is None: return self # type: ignore
        # Super __get__ calls ensure_one
        val_id = super().__get__(record, owner)
        if not val_id:
             return record.env[self.comodel_name].browse([]) # type: ignore
        return record.env[self.comodel_name].browse([val_id]) # type: ignore

class One2many(Field[list['Model']]): # Returns RecordSet (List-like)
    _type = 'one2many'
    _sql_type = None
    
    def __init__(self, comodel_name, inverse_name, string=None, **kwargs):
        super().__init__(string=string, **kwargs)
        self.comodel_name = comodel_name
        self.inverse_name = inverse_name
        self.store = False
    
    def __get__(self, record, owner) -> list['Model']:
        if record is None or not record.ids: return [] # type: ignore
        record.ensure_one()
        
        # Cache Check
        key = (record._name, record.ids[0], self.name)
        if key in record.env.cache:
            ids = record.env.cache[key]
            return record.env[self.comodel_name].browse(ids) # type: ignore
            
        raise RuntimeError(f"AsyncORM: One2many field '{self.name}' not in cache. Use await record.ensure('{self.name}').")

class Many2many(Field[list['Model']]):
    _type = 'many2many'
    _sql_type = None # No column in main table

    def __init__(self, comodel_name, string=None, relation=None, column1=None, column2=None, **kwargs):
        super().__init__(string=string, **kwargs)
        self.comodel_name = comodel_name
        self.relation = relation
        self.column1 = column1
        self.column2 = column2
        self.store = False
    
    def __get__(self, record, owner) -> list['Model']:
        if record is None or not record.ids: return [] # type: ignore
        record.ensure_one()
        
        # Cache Check
        key = (record._name, record.ids[0], self.name)
        if key in record.env.cache:
            ids = record.env.cache[key]
            return record.env[self.comodel_name].browse(ids) # type: ignore
            
        raise RuntimeError(f"AsyncORM: Many2many field '{self.name}' not in cache. Use await record.ensure('{self.name}').")

class Binary(Field[bytes]):
    _type = 'binary'
    _sql_type = None # Not stored in main table

    def __get__(self, record, owner) -> Optional[bytes]:
        if record is None: return self # type: ignore
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
