import inspect
from datetime import datetime
from typing import List, Dict, Any, Tuple
from .registry import Registry
from .fields import Field, Integer, Datetime, Many2one, One2many, Many2many, Binary, Char, Text
from .db_async import AsyncDatabase
import json
from pypika import Query, Table, Field as PypikaField, Order, Parameter

class MetaModel(type):
    def __new__(mcs, name, bases, attrs):
        inherit = attrs.get('_inherit')
        _name = attrs.get('_name')

        if inherit and not _name:
            cls = Registry.get(inherit)
            if not cls: raise TypeError(f"Model {inherit} not found")
            for key, val in attrs.items():
                if isinstance(val, Field):
                    val.name = key
                    cls._fields[key] = val
                    setattr(cls, key, val)
                elif hasattr(val, '_depends'):
                    setattr(cls, key, val)
            mcs._register_triggers(cls)
            return cls
        
        cls = super().__new__(mcs, name, bases, attrs)
        if not _name: return cls 

        fields = {}
        for key, val in attrs.items():
            if isinstance(val, Field):
                val.name = key
                fields[key] = val
                
                # Auto-configure Many2many
                if isinstance(val, Many2many) and not val.relation:
                    # Generic Odoo-style naming
                    # We need _name of model.
                    # _name is in attrs.get('_name') (checked above)
                    model_name = attrs.get('_name')
                    if model_name:
                        t1 = model_name.replace('.', '_')
                        t2 = val.comodel_name.replace('.', '_')
                        
                        # Sort for deterministic relation name
                        # (Odoo uses alphabetical order of table names)
                        lists = sorted([t1, t2])
                        val.relation = f"{lists[0]}_{lists[1]}_rel"
                        
                        # Columns: table1_id, table2_id
                        # But which is column1? column1 is for 'this' model.
                        val.column1 = f"{t1}_id"
                        val.column2 = f"{t2}_id"
        
        if 'id' not in fields:
            f = Integer(string='ID', readonly=True); f.name='id'; fields['id']=f; setattr(cls,'id',f)
        if 'create_date' not in fields:
            f = Datetime(string='Created', readonly=True); f.name='create_date'; fields['create_date']=f; setattr(cls,'create_date',f)
        if 'write_date' not in fields:
            f = Datetime(string='Updated', readonly=True); f.name='write_date'; fields['write_date']=f; setattr(cls,'write_date',f)

        cls._fields = fields
        cls._table = _name.replace('.', '_')
        cls._triggers = {}
        mcs._register_triggers(cls)

        Registry.register(_name, cls)
        return cls

    @staticmethod
    def _register_triggers(cls):
        # Map: Source Field -> Set of Target Computed Fields
        # cls._triggers = {'source_field': {'computed_field_1', 'computed_field_2'}}
        
        for name, field in cls._fields.items():
            if field.compute:
                method_name = field.compute
                if hasattr(cls, method_name):
                    method = getattr(cls, method_name)
                    # Support @api.depends decoration
                    depends = getattr(method, '_depends', [])
                    
                    for dep in depends:
                        if dep not in cls._triggers:
                            cls._triggers[dep] = set()
                        cls._triggers[dep].add(name) # Add FIELD name, not method name

class Model(metaclass=MetaModel):
    _name = None
    _description = None
    _rec_name = 'name' # Default record name field

    def __init__(self, env, ids=(), prefetch_ids=None):
        self.env = env
        self.ids = tuple(ids)
        self._prefetch_ids = prefetch_ids if prefetch_ids is not None else set(self.ids)
        self._prefetch_ids.update(self.ids)
        self._force_rules = False

    def __iter__(self):
        for id_val in self.ids:
            yield self.browse([id_val])
    
    def __len__(self):
        return len(self.ids)
    
    def __bool__(self):
        return bool(self.ids)
        
    def __await__(self):
        """
        Make RecordSet awaitable.
        Allows 'await record.partner_id' to work even if result is cached.
        returns self.
        """
        async def _self():
            return self
        return _self().__await__()
        
    def __repr__(self):
        return f"<{self._name}({self.ids})>"
    
    def __eq__(self, other):
        if not isinstance(other, Model): return False
        return self._name == other._name and set(self.ids) == set(other.ids)

    def __getitem__(self, index):
        ids = self.ids[index]
        if isinstance(ids, int):
            ids = [ids]
        return self.browse(ids)

    def __getattr__(self, name):
        # 1. Field Access (Cached)
        if name in self._fields:
             if not self.ids: return None # Empty RecordSet
             self.ensure_one()
             key = (self._name, self.ids[0], name)
             if key in self.env.cache:
                 val = self.env.cache[key]
                 field = self._fields[name]
                 if field._type == 'many2one':
                     if not val:
                         # Return empty recordset (singleton?) or None?
                         # Odoo standard: Empty RecordSet (False logic)
                         return self.env[field.comodel_name].browse([]) 
                     return self.env[field.comodel_name].browse(val)
                 elif field._type in ('one2many', 'many2many'):
                     return self.env[field.comodel_name].browse(val or [])
                 return val
             else:
                 # Async Trap: We can't await here.
                 # If value not in cache, we technically should error or return None?
                 # Odoo would lazy load. We can't.
                 # Return None or raise? Raise helps debugging.
                 raise AttributeError(f"Field '{name}' not in cache for {self}. Use await record.read(['{name}']) first.")
        
        # 2. Delegate (Method missing? No, methods are found by python first)
        raise AttributeError(f"'{self._name}' object has no attribute '{name}'")

    def ensure_one(self):
        if len(self.ids) != 1:
            raise ValueError(f"Expected singleton: {self._name}({self.ids})")
        return self

    def filtered(self, func):
        """
        Return filtered recordset.
        func: lambda rec: rec.age > 10
        """
        ids = [rec.id for rec in self if func(rec)]
        return self.browse(ids)

    async def mapped(self, field_name):
        """
        Return list of values.
        If field is relational, return recordset.
        """
        if not self.ids: return []
        
        # 1. Batch Read
        # Checking if field exists to avoid getattr magic if possible
        if field_name in self._fields:
            # Vectorized fetch
            data = await self.read([field_name])
            
            # Map results by ID to preserve order
            val_map = {r['id']: r[field_name] for r in data}
            res = [val_map.get(rid) for rid in self.ids]
            
            # Relational flattening logic
            field = self._fields[field_name]
            if field._type in ('many2one', 'one2many', 'many2many'):
                # Res is list of IDs (or tuples for M2O?)
                # read() returns:
                # M2O: (id, name) or {'_m2o_id': id, ...}
                # X2M: [id, id, ...]
                
                # Flattening
                all_ids = []
                for val in res:
                    if not val: continue
                    if isinstance(val, (list, tuple)):
                        # Handle (id, name) or [id, id]
                        if field._type == 'many2one':
                             # M2O might be {'_m2o_id': id} or (id, name)
                             if isinstance(val, dict) and '_m2o_id' in val:
                                 all_ids.append(val['_m2o_id'])
                             elif isinstance(val, tuple):
                                 all_ids.append(val[0])
                             else:
                                 # Maybe just ID?
                                 if isinstance(val, int): all_ids.append(val)
                        else:
                             # X2M is list of IDs
                             all_ids.extend(val)
                    elif isinstance(val, int):
                        all_ids.append(val)
                
                # Remove duplicates? Standard Odoo mapped does not? 
                # "The order of appropriate records is preserved."
                # Duplicates are usually removed in Odoo mapped if it returns recordset.
                
                # Use dict.fromkeys to preserve order and remove dupes
                unique_ids = list(dict.fromkeys(all_ids))
                return self.env[field.comodel_name].browse(unique_ids)
            
            return res
            
        # Fallback for non-stored/properties (slow loop but now async)
        res = []
        for rec in self:
            # We still use checking if it's a coroutine?
            # getattr(rec, field_name) will trigger __get__
            # If __get__ is sync and fully cached, it returns value.
            # If __get__ raises "Use await", we are stuck.
            # But mapped logic above handles stored fields via read().
            # So this fallback is only for pure python @property or similar.
            val = getattr(rec, field_name)
            res.append(val)
        return res

    def browse(self, ids):
        if isinstance(ids, int): ids = [ids]
        return self.env.get(self._name)._with_ids(ids, self._prefetch_ids)

    def _with_ids(self, ids, prefetch_ids=None):
        return self.__class__(self.env, tuple(ids), prefetch_ids)



    
    async def check_access_rights(self, operation):
        """
        Verify access rights using ir.model.access.
        operation: 'read', 'write', 'create', 'unlink'
        """
        if self.env.uid == 1: 
            # Security Audit: Log superuser bypass
            if operation in ('write', 'unlink'):
                print(f"AUDIT WARN: UID 1 bypassing rules for {operation} on {self._name}")
            return True
        
        # Cache Check
        cache_key = (self._name, operation)
        if cache_key in self.env.permission_cache:
            return self.env.permission_cache[cache_key]

        if self._name.startswith('ir.'):
             self.env.permission_cache[cache_key] = True
             return True 

        # Check ACL
        perm_map = {
            'read': 'perm_read',
            'write': 'perm_write',
            'create': 'perm_create',
            'unlink': 'perm_unlink'
        }
        col = perm_map.get(operation)
        if not col: return True
        
        # Get User Groups (Transitive)
        user_groups = []
        try:
            # We access res.users dynamically to avoid circular imports
            if Registry.get('res.users'):
                user = self.env['res.users'].browse(self.env.uid)
                if hasattr(user, 'get_group_ids'):
                    user_groups = await user.get_group_ids()
        except Exception as e:
            # Fallback if something breaks during boot or early init
            print(f"Access Check Warning: Could not fetch groups: {e}")
            pass
            
        # Global Cache Check
        from .security import AccessCache
        # Tuple must be hashable and sorted for consistency
        # Ensure no None values
        safe_groups = [g for g in user_groups if g is not None]
        groups_key = tuple(sorted(safe_groups)) if safe_groups else ()
        global_key = (groups_key, self._name, operation)
        
        cached_result = await AccessCache.get(global_key)
        if cached_result is not None:
             self.env.permission_cache[cache_key] = cached_result
             if cached_result:
                 return True
             else:
                 raise Exception(f"Access Denied: You cannot {operation} document {self._name}")

        cr = self.env.cr
        from .tools.sql import SQLParams
        sql = SQLParams()
        
        if user_groups:
            # Native SQL Params ($n)
            placeholders = sql.add_many(user_groups)
            group_clause = f"(a.group_id IS NULL OR a.group_id IN ({placeholders}))"
        else:
            group_clause = "a.group_id IS NULL"

        # Model Param
        p_model = sql.add(self._name)
        
        query = f"""
            SELECT 1 FROM ir_model_access a 
            JOIN ir_model m ON a.model_id = m.id
            WHERE m.model = {p_model} AND a.{col} = TRUE
            AND {group_clause}
            LIMIT 1
        """
        await cr.execute(query, sql.get_params())
        if cr.fetchone():
            self.env.permission_cache[cache_key] = True
            await AccessCache.set(global_key, True)
            return True
            
        # Cache Negative Result too
        await AccessCache.set(global_key, False)
        raise Exception(f"Access Denied: You cannot {operation} document {self._name}")

    def name_get(self):
        """
        Returns [(id, name), ...]
        """
        res = []
        for record in self:
            name = f"{record._name},{record.id}"
            if self._rec_name and self._rec_name in record._fields:
                 val = getattr(record, self._rec_name)
                 if val: name = str(val)
            res.append((record.id, name))
        return res

    def default_get(self, fields_list):
        defaults = {}
        for fname in fields_list:
            if fname in self._fields:
                field = self._fields[fname]
                if hasattr(field, 'default'):
                    val = field.default
                    if callable(val):
                        defaults[fname] = val()
                    else:
                        defaults[fname] = val
        return defaults

    
    async def _apply_ir_rules(self, operation='read', param_builder=None):
        """
        Fetch and evaluate rules.
        Returns: Pypika Criterion (or None).
        
        NOTE: Calling code must handle None.
        If param_builder provided, placeholders are managed there.
        """
        if self.env.uid == 1 and not self._force_rules: # Allow forcing rules even for admin if needed? No standard.
            return None
            
        if self._name == 'ir.rule':
             return None

        # Direct SQL to avoid recursion hell
        perm_map = {
            'read': 'perm_read',
            'write': 'perm_write',
            'create': 'perm_create',
            'unlink': 'perm_unlink'
        }
        col = perm_map.get(operation, 'perm_read')
        
        from .tools.sql import SQLParams
        # We need a builder for the rule query itself
        sql = SQLParams()
        p_model = sql.add(self._name)
        
        query = f"""
            SELECT r.domain_force FROM ir_rule r
            JOIN ir_model m ON r.model_id = m.id
            WHERE m.model = {p_model} AND r.active = True AND r.{col} = True
        """
        await self.env.cr.execute(query, sql.get_params())
        rows = self.env.cr.fetchall()
        
        if not rows:
            return None
            
        from .tools.domain_parser import DomainParser
        parser = DomainParser()
        
        # Pypika Table
        from pypika import Table
        
        global_domains = []
        user_obj = self.env.user 
        eval_context = {
            'user': user_obj,
            'company': self.env.company,
            'time': datetime,
            'datetime': datetime
        }
        
        from .tools.safe_eval import safe_eval

        for r in rows:
            domain_str = r[0]
            if not domain_str: continue
            try:
                d = safe_eval(domain_str, eval_context)
                global_domains.append(d)
            except Exception as e:
                print(f"Rule Eval Error on {self._name}: {e}")
                
        if not global_domains:
            return None
            
        # Combine Criteria
        full_criterion = None
        
        # Pypika Table for the current model
        p_table = Table(self._table)

        for d in global_domains:
            # We must use the caller's param_builder if available
            # If not, we create one locally? 
            # If caller didn't provide param_builder, we can't easily return just a criterion 
            # because parameters would be lost?
            # Actually, this refactor assumes caller provides param_builder or we handle it.
            # For backward compat, if no param_builder, we might need to return (sql, params).
            # BUT we are changing all callers. So let's enforce param_builder or Create one?
            # If we create one, we must return parameters.
            # Let's support both modes but prefer Pypika Object return.
            
            crit = parser.parse_pypika(d, p_table, param_builder)
            if crit:
                if full_criterion is None:
                    full_criterion = crit
                else:
                    full_criterion = full_criterion & crit
                
        return full_criterion

    def _validate_order(self, order):
        if not order: return None
        
        safe_parts = []
        parts = order.split(',')
        
        for part in parts:
            part = part.strip()
            if not part: continue
            
            tokens = part.split()
            if len(tokens) > 2:
                # e.g. "name desc extra" -> INVALID
                raise ValueError(f"Invalid Order Clause: {part}")
            
            field_name = tokens[0]
            direction = tokens[1].upper() if len(tokens) > 1 else 'ASC'
            
            # 1. Validate Field
            # id, create_date, write_date should be accepted even if not in _fields
            if field_name not in self._fields and field_name not in ('id', 'create_date', 'write_date'):
                 raise ValueError(f"Security Error: Invalid Order Field '{field_name}' for model {self._name}")
            
            # 2. Validate Direction
            if direction not in ('ASC', 'DESC'):
                 raise ValueError(f"Security Error: Invalid Order Direction '{direction}'")
                 
            safe_parts.append(f'"{field_name}" {direction}')
            
        return ", ".join(safe_parts)

    async def _get_restricted_fields(self):
        """
        Returns {field_name: set(group_ids)}
        """
        key = (self._name, '_restricted_fields')
        if key in self.env.cache:
            return self.env.cache[key]
            
        # 1. Get Model ID
        from .tools.sql import SQLParams
        sql = SQLParams()
        p_model = sql.add(self._name)
        
        await self.env.cr.execute(f"SELECT id FROM ir_model WHERE model = {p_model}", sql.get_params())
        res = self.env.cr.fetchone()
        if not res: return {}
        model_id = res[0]
        
        # 2. Get Fields with Groups
        sql2 = SQLParams()
        p_mid = sql2.add(model_id)
        
        query = f"""
            SELECT f.name, r.res_groups_id 
            FROM ir_model_fields f
            JOIN ir_model_fields_group_rel r ON f.id = r.ir_model_fields_id
            WHERE f.model_id = {p_mid}
        """
        # Important: Verify table name. If not created yet, this fails gracefully?
        # We wrap in try-except to avoid breaking bootstrap
        try:
            await self.env.cr.execute(query, sql2.get_params())
            rows = self.env.cr.fetchall()
        except Exception as e:
            # Table might not exist yet during init
            return {}

        res_map = {}
        for fname, gid in rows:
            if fname not in res_map: res_map[fname] = set()
            res_map[fname].add(gid)
            
        self.env.cache[key] = res_map
        return res_map



    async def _filter_authorized_fields(self, operation, fields):
        # Async Version matching the Signature
        return fields

    async def _write_binary(self, record, values):
        # Implementation needed for create/write
        pass

    async def search(self, domain, offset=0, limit=None, order=None, include=None, cursor=None):
        from .tools.domain_parser import DomainParser
        
        await self.check_access_rights('read')
        
        from .tools.sql import SQLParams
        sql = SQLParams() # Parameter Collector
        
        # Pypika Table
        from pypika import Table, Order
        t = Table(self._table)
        q = Query.from_(t).select(t.id)

        # Cursor Pagination Logic
        search_domain = (domain or []).copy()
        if cursor:
             search_domain.append(('id', '>', cursor))

        # 1. Base Domain
        parser = DomainParser()
        base_criterion = parser.parse_pypika(search_domain, t, param_builder=sql)
        
        # 2. Apply Security Rules
        rule_criterion = await self._apply_ir_rules('read', param_builder=sql)
        
        # Combine
        final_criterion = base_criterion
        if rule_criterion:
            if final_criterion:
                final_criterion = final_criterion & rule_criterion
            else:
                final_criterion = rule_criterion
        
        if final_criterion:
            q = q.where(final_criterion)
        
        # Order By
        if order:
            # We reuse _validate_order but need to parse it for Pypika or use custom string?
            # Pypika allows raw string only via special methods or we parse standard Odoo syntax "field desc, field2 asc"
            # Let's parse it safely.
            parts = order.split(',')
            for part in parts:
                part = part.strip()
                if not part: continue
                tokens = part.split()
                f_name = tokens[0]
                direction = tokens[1].upper() if len(tokens) > 1 else 'ASC'
                
                # Security Check (Basic check vs _fields)
                if f_name not in self._fields and f_name not in ('id', 'create_date', 'write_date'):
                     continue # Ignore invalid fields to avoid crash or injection risk via Order
                
                # Determine Pypika Field
                # If f_name is just 'name', t.name.
                p_field = t[f_name]
                p_order = Order.desc if direction == 'DESC' else Order.asc
                q = q.orderby(p_field, order=p_order)
        
        if limit:
            q = q.limit(limit)
            
        if offset:
            q = q.offset(offset)
        
        # Execute
        # get_sql generates the SQL string. We have params in `sql`.
        query_str = q.get_sql()
        
        await self.env.cr.execute(query_str, sql.get_params())
        res = self.env.cr.fetchall()
        
        res_ids = []
        for r in res:
            # Pypika / DB returns tuple or Record. Access by index 0.
            if isinstance(r, (tuple, list)):
                res_ids.append(r[0])
            else:
                # AsyncPG Record?
                res_ids.append(r['id'])

        records = self.browse(res_ids)
        
        if include and res_ids:
            await records.read(include)
            
        return records

    async def check_access_rule(self, operation):
        """
        Verifies that the current records satisfy the Record Rules.
        Raises AccessError if any record is forbidden.
        """
        if self.env.uid == 1 and not self._force_rules: return
        if not self.ids: return
        
        from .tools.sql import SQLParams
        
        # 1. Prepare Rule Criterion
        rule_builder = SQLParams()
        rule_criterion = await self._apply_ir_rules(operation, param_builder=rule_builder)
        
        if not rule_criterion: return

        # Verify all IDs match the rule
        all_ids = list(self.ids)
        total_requested = len(all_ids)
        total_matched = 0
        
        from pypika import Table, functions
        t = Table(self._table)
        
        chunk_size = 1000
        for i in range(0, total_requested, chunk_size):
            chunk = all_ids[i:i + chunk_size]
            
            # Create a Chunk Builder starting where rule_builder left off
            chunk_builder = SQLParams(start_index=rule_builder.index)
            # Copy pre-existing rule params
            chunk_builder.params = list(rule_builder.params)
            
            # Helper: Add IDs
            id_params = []
            for id_val in chunk:
                 id_params.append(Parameter(chunk_builder.add(id_val)))
            
            q = Query.from_(t).select(functions.Count('*')).where(rule_criterion).where(t.id.isin(id_params))
            
            query = q.get_sql()
            
            await self.env.cr.execute(query, chunk_builder.get_params())
            res = self.env.cr.fetchone()
            if res:
                total_matched += res[0]
        
        if total_matched != total_requested:
             raise Exception(f"Access Rule Violation: One or more records in {self._name} are restricted for operation '{operation}'.")

    async def ensure(self, fields_to_ensure):
        """
        Ensure specified names are in cache.
        Wrapper around read() but cleaner semantic.
        Usage: await record.ensure(['partner_id', 'line_ids'])
        """
        if isinstance(fields_to_ensure, str): fields_to_ensure = [fields_to_ensure]
        
        # Filter what is missing
        missing = [f for f in fields_to_ensure if (self._name, self.ids[0], f) not in self.env.cache]
        if missing:
             # read populates cache
             await self.read(missing)

    async def read(self, fields=None):
        """
        Read fields for current ids.
        Returns list of dictionaries.
        """
        await self.check_access_rights('read')
        if not self.ids: return []
        
        # Field Level Security
        if fields:
            fields = await self._filter_authorized_fields('read', fields)
        
        # If fields is None, read all stored fields
        if fields is None:
            fields = [f for f in self._fields if self._fields[f]._sql_type]
            
        # Pypika Setup
        from pypika import Table, Parameter
        t = Table(self._table)
        from .tools.sql import SQLParams
        
        # 1. Main Query Rule Setup
        rule_builder = SQLParams()
        rule_criterion = await self._apply_ir_rules('read', param_builder=rule_builder)
        
        # Filter valid SQL columns
        sql_fields = [f for f in fields if f in self._fields and self._fields[f]._sql_type]
        
        
        rows = []
        if sql_fields:
             if 'id' not in sql_fields: sql_fields.insert(0, 'id')
             
             # Use Pypika Select
             q = Query.from_(t).select(*sql_fields)
             
             main_builder = SQLParams(start_index=rule_builder.index)
             main_builder.params = list(rule_builder.params)
             
             ids_input = list(self.ids)
             id_params = []
             for id_val in ids_input:
                  id_params.append(Parameter(main_builder.add(id_val)))
 
             q = q.where(t.id.isin(id_params))
             if rule_criterion:
                  q = q.where(rule_criterion)
                  
             await self.env.cr.execute(q.get_sql(), main_builder.get_params())
             rows = self.env.cr.fetchall() 
        
        # Map by ID
        rows_map = {r['id']: r for r in rows}
        
        for id_val in self.ids:
            if id_val in rows_map:
                row = rows_map[id_val]
                # Update Cache
                for f in sql_fields:
                    self.env.cache[(self._name, id_val, f)] = row[f]
        
        # 2. Relational Prefetching (N+1 Fix / Pypika Refactor)
        relational_fields = [f for f in fields if f in self._fields and not self._fields[f]._sql_type]
        
        for f in relational_fields:
            field = self._fields[f]
            ids_to_fetch = [rid for rid in self.ids if (self._name, rid, f) not in self.env.cache]
            if not ids_to_fetch: continue
            
            if isinstance(field, Many2many):
                if not field.relation: continue
                
                # M2M Query
                sql_m2m = SQLParams()
                # Pypika
                t_rel = Table(field.relation)
                p_ids = [Parameter(sql_m2m.add(i)) for i in ids_to_fetch]
                
                q = Query.from_(t_rel).select(field.column1, field.column2).where(t_rel[field.column1].isin(p_ids))
                
                await self.env.cr.execute(q.get_sql(), sql_m2m.get_params())
                relations = self.env.cr.fetchall()
                
                rel_map = {rid: [] for rid in ids_to_fetch}
                for src, dest in relations:
                    if src in rel_map:
                        rel_map[src].append(dest)
                
                for rid, vals_list in rel_map.items():
                    self.env.cache[(self._name, rid, f)] = vals_list
                    
            elif isinstance(field, One2many):
                Comodel = self.env[field.comodel_name]
                inv_field = field.inverse_name
                
                if inv_field not in Comodel._fields: continue
                inv_col = Comodel._fields[inv_field].name
                
                # O2M Query
                sql_o2m = SQLParams()
                t_co = Table(Comodel._table)
                p_ids = [Parameter(sql_o2m.add(i)) for i in ids_to_fetch]
                
                q = Query.from_(t_co).select(t_co.id, t_co[inv_col]).where(t_co[inv_col].isin(p_ids))
                
                await self.env.cr.execute(q.get_sql(), sql_o2m.get_params())
                relations = self.env.cr.fetchall()
                
                rel_map = {rid: [] for rid in ids_to_fetch}
                for child_id, parent_id in relations:
                    if parent_id in rel_map:
                        rel_map[parent_id].append(child_id)
                        
                for rid, vals_list in rel_map.items():
                    self.env.cache[(self._name, rid, f)] = vals_list

        
        # Collect M2O to resolve
        results = []
        m2o_to_resolve = {} # {model: {id, ...}}
        
        for id_val in self.ids:
            vals = {'id': id_val}
            for f in fields:
                if f in self._fields:
                     field = self._fields[f]
                     if (self._name, id_val, f) in self.env.cache:
                         val = self.env.cache[(self._name, id_val, f)]
                         
                         if isinstance(field, Many2one):
                             if val:
                                 if field.comodel_name not in m2o_to_resolve:
                                     m2o_to_resolve[field.comodel_name] = set()
                                 m2o_to_resolve[field.comodel_name].add(val)
                                 vals[f] = {'_m2o_id': val, '_model': field.comodel_name} # Placeholder
                             else:
                                 vals[f] = False
                         elif isinstance(field, (One2many, Many2many)):
                             vals[f] = val if val else []
                         else:
                             vals[f] = val
                     else:
                         vals[f] = None
            results.append(vals)

        # Resolve Names
        resolved_names = {} # {model: {id: name}}
        for model_name, ids in m2o_to_resolve.items():
            if not ids: continue
            Comodel = self.env[model_name]
            # Name Search / Read Name
            # Assuming 'name' field exists or rec_name
            # Optimally: search_read or name_get equivalent
            # For now, simple read of 'name'
            names = await Comodel.browse(list(ids)).read(['name'])
            resolved_names[model_name] = {r['id']: r.get('name', 'Unnamed') for r in names}
            
        # Fill Placeholders
        for res in results:
            for k, v in res.items():
                if isinstance(v, dict) and '_m2o_id' in v:
                    mid = v['_m2o_id']
                    mmodel = v['_model']
                    name = resolved_names.get(mmodel, {}).get(mid, 'Unknown')
                    res[k] = (mid, name)
                    
        return results

    async def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None, cursor=None):
        """
        Hyper-Optimized: Single Query with Automatic Joins for Names.
        Returns: [{'id': 1, 'partner_id': (5, 'Agrolait')}, ...]
        """
        await self.check_access_rights('read')
        
        # 1. Definir campos a leer
        if fields:
            fields = await self._filter_authorized_fields('read', fields)
        else:
            fields = [f for f in self._fields if self._fields[f]._sql_type]
        
        if 'id' not in fields: fields.insert(0, 'id')

        # 2. Preparar Setup de Query
        from .tools.sql import SQLParams
        from .tools.domain_parser import DomainParser
        
        sql = SQLParams()
        col_map = {}
        select_parts = []
        joins_parts = []
        
        # 3. Selección Inteligente de Columnas + JOINs
        for fname in fields:
            if fname not in self._fields: continue
            field = self._fields[fname]
            
            if field._type == 'many2one':
                # AUTOMATIC JOIN: Traemos el ID y el Name de la tabla relacionada
                comodel_name = field.comodel_name
                if comodel_name in self.env.registry:
                    comodel = self.env[comodel_name]
                    join_table = comodel._table
                    alias = f"{fname}_rel"
                    
                    # Add LEFT JOIN
                    joins_parts.append(f'LEFT JOIN "{join_table}" AS "{alias}" ON "{self._table}"."{fname}" = "{alias}".id')
                    
                    # Select ID and Name from Alias
                    alias_id = f"{fname}_vals_id"
                    alias_name = f"{fname}_vals_name"
                    
                    select_parts.append(f'"{alias}".id AS "{alias_id}", "{alias}".name AS "{alias_name}"')
                    col_map[fname] = {'type': 'm2o', 'id': alias_id, 'name': alias_name}
                else:
                    # Fallback si modelo no existe
                    select_parts.append(f'"{self._table}"."{fname}"')
                    col_map[fname] = {'type': 'raw', 'col': fname}
            
            elif field._sql_type:
                # Campo normal
                select_parts.append(f'"{self._table}"."{fname}"')
                col_map[fname] = {'type': 'raw', 'col': fname}

        # 4. Aplicar Domain (WHERE)
        parser = DomainParser()
        where_clause, _ = parser.parse(domain or [], param_builder=sql)
        
        # Aplicar Reglas de Seguridad
        rule_clause, _ = await self._apply_ir_rules('read', param_builder=sql)
        final_where = f"({where_clause})"
        if rule_clause: final_where += f" AND ({rule_clause})"

        # Construct Query
        select_sql = ", ".join(select_parts)
        join_sql = " ".join(joins_parts)
        query = f'SELECT {select_sql} FROM "{self._table}" {join_sql} WHERE {final_where}'
        
        # Order / Limit / Offset
        if order: 
            safe_order = self._validate_order(order)
            if safe_order: query += f" ORDER BY {safe_order}"
        if limit: query += f" LIMIT {limit}"
        if offset: query += f" OFFSET {offset}"

        # 5. Ejecutar
        await self.env.cr.execute(query, sql.get_params())
        rows = self.env.cr.fetchall()

        # 6. Formatear Respuesta (Tuple Construction)
        results = []
        for row in rows:
            res = {}
            for fname, meta in col_map.items():
                if meta['type'] == 'raw':
                    res[fname] = row[fname]
                elif meta['type'] == 'm2o':
                    rid = row[meta['id']]
                    rname = row[meta['name']]
                    res[fname] = (rid, rname) if rid else False
            results.append(res)
            
        return results



    async def _search_read_optimized(self, domain, fields, offset, limit, order, join_fields):
        from .tools.domain_parser import DomainParser
        from .tools.sql import SQLParams
        from pypika import Table, Order, Field as PypikaField
        
        t = Table(self._table)
        q = Query.from_(t).select(t.id)
        
        # Select Simple Fields
        for f in fields:
            if f in self._fields and self._fields[f]._sql_type and f not in [j[0] for j in join_fields]:
                q = q.select(t[f])
                
        # Handle Joins
        # M2O: LEFT JOIN comodel c ON t.field = c.id
        # Select: c.id, c.name (OR rec_name)
        
        # Map for result processing
        # {field_name: { 'alias_id': 'alias_id', 'alias_name': 'alias_name' }}
        join_map = {} 
        
        for fname, field in join_fields:
            Comodel = self.env[field.comodel_name]
            t_co = Table(Comodel._table)
            
            # Unique Alias for Join Table
            alias = f"{fname}_join"
            t_join = t_co.as_(alias)
            
            q = q.left_join(t_join).on(t[fname] == t_join.id)
            
            # Select ID and Name
            col_id = f"{fname}_id_val"
            col_name = f"{fname}_name_val"
            
            q = q.select(t_join.id.as_(col_id))
            # Assuming 'name' field exists on Comodel for now
            # TODO: robust rec_name support
            q = q.select(t_join.name.as_(col_name))
            
            join_map[fname] = {'id': col_id, 'name': col_name}
            
            # Also select the raw foreign key on main table?
            # It's already checked via 't[f]'? 
            # If we requested 'partner_id', we want (id, name).
            # We don't need t.partner_id unless for debugging.
            
        # Domain (Base + Security)
        sql = SQLParams()
        parser = DomainParser()
        # TODO: parser needs to use 't' (main table) aliases?
        # Our parser uses plain field names. Pypika will resolve to 't' if only 1 table.
        # But we Joined.
        # DomainParser might generate "field", which is ambiguous?
        # Pypika usually handles "field" as belonging to FROM table if unambiguous.
        # But if Joined tables have same fields?
        # DomainParser current impl uses f'"{field}" {op} %s'.
        # This is raw SQL string criterion.
        # 'SELECT ... FROM t ... WHERE "field" = $1'.
        # If "field" exists in joined table, it's ambiguous.
        # Usually M2O fields are unique to model.
        # But 'name', 'create_date' exist in both.
        # We must prefix with table alias: "table"."field".
        # DomainParser needs update to accept Table alias?
        # parser.parse_pypika(..., table=t).
        # Yes, I updated parse_pypika to take 'table'.
        
        base_criterion = parser.parse_pypika(domain or [], t, param_builder=sql)
        rule_criterion = await self._apply_ir_rules('read', param_builder=sql) # Rules usually on 'read'
        
        if base_criterion: q = q.where(base_criterion)
        if rule_criterion: q = q.where(rule_criterion)
        
        # Order
        if order:
            parts = order.split(',')
            for part in parts:
                part = part.strip()
                if not part: continue
                tokens = part.split()
                f_name = tokens[0]
                direction = tokens[1].upper() if len(tokens) > 1 else 'ASC'
                if f_name in self._fields:
                    p_order = Order.desc if direction == 'DESC' else Order.asc
                    q = q.orderby(t[f_name], order=p_order)
                    
        if limit: q = q.limit(limit)
        if offset: q = q.offset(offset)
        
        await self.env.cr.execute(q.get_sql(), sql.get_params())
        rows = self.env.cr.fetchall()
        
        # Process Results
        results = []
        for r in rows:
            # r is asyncpg Record (dict-like)
            res = {}
            # ID
            res['id'] = r['id']
            
            for f in fields:
                if f == 'id': continue
                
                if f in join_map:
                    # M2O Joined
                    jid = r.get(join_map[f]['id'])
                    jname = r.get(join_map[f]['name'])
                    if jid:
                        res[f] = (jid, jname)
                    else:
                        res[f] = False
                elif f in self._fields:
                    # Simple Field
                    res[f] = r.get(f) # might use alias if collision?
                    # Pypika select(t[f]) uses 'f' as name unless aliased.
                    
            results.append(res)
            
        return results

    def _process_one2many(self, record, field_name, commands):
        """
        Process O2M commands:
        (0, 0, vals) -> Create
        (1, id, vals) -> Write
        (2, id) -> Delete (Unlink)
        (4, id, _) -> Link
        (6, 0, [ids]) -> Set Link
        """
        field = self._fields[field_name]
        Comodel = self.env[field.comodel_name]
        
        if commands is None: return

        for cmd in commands:
            if not isinstance(cmd, (list, tuple)): continue
            op = cmd[0]
            
            if op == 0: # Create
                vals = cmd[2]
                vals[field.inverse_name] = record.id
                Comodel.create(vals)
            elif op == 1: # Write
                res_id = cmd[1]
                vals = cmd[2]
                Comodel.browse([res_id]).write(vals)
            elif op == 2: # Delete
                res_id = cmd[1]
                Comodel.browse([res_id]).unlink()
            elif op == 4: # Link
                res_id = cmd[1]
                Comodel.browse([res_id]).write({field.inverse_name: record.id})
            elif op == 6: # Set
                ids = cmd[2]
                # Unlink others
                existing = Comodel.search([(field.inverse_name, '=', record.id)])
                existing.write({field.inverse_name: None}) # Or unlink?
                # Link new
                Comodel.browse(ids).write({field.inverse_name: record.id})

    def onchange(self, vals, field_name, field_onchange):
        """
        Simulate onchange in memory.
        vals: Current form values (including O2M commands as list of tuples)
        """
        snapshot = Snapshot(self, vals)
        
        method_name = field_onchange.get(field_name)
        if method_name:
            # Re-bind method to snapshot so 'self' inside method refers to snapshot
            # 1. Get unbound function
            func = getattr(self.__class__, method_name)
            # 2. Bind to snapshot
            method = func.__get__(snapshot, self.__class__)
            
            method()
            
            # Collect changes
            changes = {}
            for k in snapshot._changed:
                changes[k] = snapshot._values[k]
            return {'value': changes}
            
        return {}




    async def _notify_change(self, operation):
        """
        Send Real-Time Notification via Postgres Channel.
        """
        if not self.ids: return
        try:
            payload = json.dumps({
                "model": self._name,
                "ids": list(self.ids),
                "type": operation,
                "uid": self.env.uid
            })
            # Use param to prevent syntax issues/injection
            await self.env.cr.execute("SELECT pg_notify('record_change', $1)", (payload,))
        except Exception as e:
            print(f"Notification Error: {e}")

    async def create(self, vals_list):
        """
        Create new record(s).
        vals_list: Dict or List of Dicts.
        Returns: RecordSet of created records.
        """
        await self.check_access_rights('create')
        
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
            
        # 1. Apply Defaults & Pre-process
        # We need a unified set of keys for the Batch Insert
        # But we must apply defaults first to know all keys.
        
        # Optimization: Scan fields with defaults once? 
        # Or just loop. 1000 records is small for Python loop.
        
        default_fields = [k for k, f in self._fields.items() if hasattr(f, 'default')]
        
        processed_vals_list = []
        
        for vals in vals_list:
            # Copy to avoid mutating input check
            v = vals.copy()
            for k in default_fields:
                if k not in v:
                    field = self._fields[k]
                    default = field.default
                    if callable(default):
                         v[k] = default()
                    else:
                         v[k] = default
            processed_vals_list.append(v)
            
        # 2. Separate formatting (Relations vs SQL)
        # We need to extract M2M/O2M/Binary for POST-INSERT processing
        # And keep only SQL fields for INSERT
        
        sql_vals_list = []
        relation_data = [] # List of (index, m2m, o2m, binary)
        
        # Identify UNION of all keys that are valid SQL columns
        # To ensure all rows have same columns for INSERT statement
        all_keys = set()
        for v in processed_vals_list:
            all_keys.update(v.keys())
            
        valid_cols = sorted([k for k in all_keys if k in self._fields and self._fields[k]._sql_type])
        
        # Robust ID Handling:
        # If 'id' is in valid_cols (e.g. passed as None), but no record has a real value,
        # remove it so Postgres uses the SERIAL default.
        if 'id' in valid_cols:
             has_id = any(v.get('id') is not None for v in processed_vals_list)
             if not has_id:
                 valid_cols.remove('id')
        
        for idx, vals in enumerate(processed_vals_list):
            m2m = {}
            o2m = {}
            binary = {}
            
            # Extract non-SQL fields
            for k, field in self._fields.items():
                if k in vals:
                     if isinstance(field, Many2many):
                         m2m[k] = vals[k]
                     elif isinstance(field, One2many):
                         o2m[k] = vals[k]
                     elif isinstance(field, Binary):
                         binary[k] = vals[k]
            
            relation_data.append({
                'm2m': m2m, 'o2m': o2m, 'binary': binary
            })
            
            # Prepare SQL Dict (filling missing with None)
            row = {}
            for col in valid_cols:
                row[col] = vals.get(col, None)
            sql_vals_list.append(row)

        # 3. Batch Insert
        created_ids = []
        
        if not sql_vals_list:
             # Empty inserts (default values)
             for _ in processed_vals_list:
                 await self.env.cr.execute(f'INSERT INTO "{self._table}" DEFAULT VALUES RETURNING id')
                 res = self.env.cr.fetchone()
                 created_ids.append(res['id'])
        else:
            # Pypika Insert
            from pypika import Table, Parameter
            t = Table(self._table)
            
            # Columns
            # Pypika .columns('a', 'b') works with strings
            q = Query.into(t).columns(*valid_cols)
            
            from .tools.sql import SQLParams
            sql = SQLParams()
            
            # Add Rows
            for row in sql_vals_list:
                row_values = []
                for c in valid_cols:
                    # Get value
                     val = row[c]
                     # Add to params, get $n
                     ph = sql.add(val)
                     # Add Parameter wrapper for Pypika
                     row_values.append(Parameter(ph))
                
                q = q.insert(*row_values)
            
            # RETURNING id (Postgres specific in Pypika)
            q = q.returning(t.id)
            
            await self.env.cr.execute(q.get_sql(), sql.get_params())
            
            rows = self.env.cr.fetchall()
            created_ids = [r['id'] for r in rows]

        # 4. Update Cache (Batch)
        for idx, new_id in enumerate(created_ids):
             row = sql_vals_list[idx] if sql_vals_list else {}
             for col, val in row.items():
                 self.env.cache[(self._name, new_id, col)] = val
                 
        records = self.browse(created_ids)
        
        # 5. Process Relations (Batch Optimization)
        # Collect operations
        m2m_batch = {} # field -> [(rid, val)]
        o2m_batch = {} # field -> [(rid, val)]
        binary_batch = [] # (record, val)
        
        for idx, r_data in enumerate(relation_data):
            rid = created_ids[idx]
            for f, v in r_data['m2m'].items():
                if f not in m2m_batch: m2m_batch[f] = []
                m2m_batch[f].append((rid, v))
            
            for f, v in r_data['o2m'].items():
                if f not in o2m_batch: o2m_batch[f] = []
                o2m_batch[f].append((rid, v))
                
            if r_data['binary']:
                binary_batch.append((records[idx], r_data['binary']))

        # Execute M2M (Bulk Insert)
        for field_name, ops in m2m_batch.items():
            f_obj = self._fields[field_name]
            to_insert = []
            
            for rid, val in ops:
                # Handle Odoo Commands [(6, 0, ids)] or Raw IDs
                target_ids = val
                if isinstance(val, list) and val and isinstance(val[0], tuple):
                    # Simple command parser
                    for cmd in val:
                        if cmd[0] == 6: target_ids = cmd[2]
                
                # Make iterable
                if not isinstance(target_ids, (list, tuple)): target_ids = [target_ids]
                
                for tid in target_ids:
                    to_insert.append((rid, tid))
            
            if to_insert:
                await self.env.cr.executemany(f'INSERT INTO "{f_obj.relation}" ("{f_obj.column1}", "{f_obj.column2}") VALUES ($1, $2)', to_insert)

        # Execute O2M (Iterative fallback or Batch Update)
        # O2M usually involves complex creates or updates. Safer to loop or delegate.
        # But we can optimize basic "updating keys" if val is list of IDs?
        # Assuming defaults for now. Use loop for O2M safety/complexity balance.
        for field_name, ops in o2m_batch.items():
             for rid, val in ops:
                 # Re-browse to get record context if needed, or pass ID
                 # _process_one2many usually needs record
                 rec = self.browse([rid])
                 await self._process_one2many(rec, field_name, val)

        # Execute Binary (Loop)
        for record, val in binary_batch:
            await self._write_binary(record, val)
        
        # 6. Trigger Compute
        all_keys = set()
        for v in processed_vals_list:
            all_keys.update(v.keys())
        
        records._modified(list(all_keys))
        await records.recompute()
                     
        await records._notify_change('create')
        return records

    async def _write_db(self, vals):
        """
        Low-level write to DB without triggering recompute logic.
        Used by caching, recompute engine, and write() itself.
        """
        if not self.ids: return True
        
        m2m_values = {}
        o2m_values = {}
        binary_values = {}
        
        # Note: Access Rights should be checked by caller (write())
        
        for k, v in list(vals.items()):
            if k in self._fields:
                field = self._fields[k]
                if isinstance(field, Many2many):
                    m2m_values[k] = vals.pop(k)
                elif isinstance(field, One2many):
                    o2m_values[k] = vals.pop(k)
                elif isinstance(field, Binary):
                    binary_values[k] = vals.pop(k)

        vals['write_date'] = datetime.now()
        valid_cols = [k for k in vals if k in self._fields and self._fields[k]._sql_type]
        
        if valid_cols:
            from .tools.sql import SQLParams
            sql = SQLParams()
            
            # Pypika Update
            from pypika import Table, Parameter
            t = Table(self._table)
            q = Query.update(t)
            
            # SET clause
            for k in valid_cols:
                 p = sql.add(vals[k])
                 q = q.set(t[k], Parameter(p))
            
            # WHERE clause
            ids_list = list(self.ids)
            id_params = []
            for id_val in ids_list:
                id_params.append(Parameter(sql.add(id_val)))
            
            q = q.where(t.id.isin(id_params))
            
            await self.env.cr.execute(q.get_sql(), sql.get_params())
            
            for id_val in self.ids:
                for k, v in vals.items():
                    self.env.cache[(self._name, id_val, k)] = v
        
        if m2m_values:
            for field, target_ids in m2m_values.items():
                f_obj = self._fields[field]
                if not target_ids: target_ids = []
                
                # Delta Logic (Simplified execution for Async)
                # 1. Get existing
                q_get = f'SELECT "{f_obj.column1}", "{f_obj.column2}" FROM "{f_obj.relation}" WHERE "{f_obj.column1}" = ANY(%s)'
                await self.env.cr.execute(q_get, (list(self.ids),))
                existing = self.env.cr.fetchall()
                
                existing_map = {}
                for rid, tid in existing:
                    if rid not in existing_map: existing_map[rid] = set()
                    existing_map[rid].add(tid)
                    
                to_insert = []
                to_delete_params = [] 
                
                # Logic for Odoo Commands: (6,0,ids), (4,id), (3,id), (5,0,0)
                # target_ids is the list of commands or flat list of IDs
                
                cmds = target_ids
                if cmds and isinstance(cmds, list) and isinstance(cmds[0], int):
                    # Flat list -> Treat as replace (6, 0, cmds)
                    cmds = [(6, 0, cmds)]
                
                for rid in self.ids:
                    current_set = existing_map.get(rid, set())
                    new_set = current_set.copy()
                    
                    for cmd in cmds:
                        if isinstance(cmd, (tuple, list)):
                            code = cmd[0]
                            if code == 6: # Replace: (6, 0, [ids])
                                new_set = set(cmd[2])
                            elif code == 4: # Add: (4, id, _)
                                new_set.add(cmd[1])
                            elif code == 3: # Remove: (3, id, _)
                                new_set.discard(cmd[1])
                            elif code == 5: # Unlink All: (5, 0, 0)
                                new_set.clear()
                                
                    adding = new_set - current_set
                    removing = current_set - new_set
                    
                    for tid in adding: to_insert.append((rid, tid))
                    for tid in removing: to_delete_params.append((rid, tid))
                         
                t_rel = Table(f_obj.relation)
                c1 = f_obj.column1
                c2 = f_obj.column2
                
                if to_delete_params:
                     q_del = Query.from_(t_rel).where(t_rel[c1] == Parameter('$1')).where(t_rel[c2] == Parameter('$2')).delete()
                     await self.env.cr.executemany(q_del.get_sql(), to_delete_params)
 
                if to_insert:
                     q_ins = Query.into(t_rel).columns(c1, c2).insert(Parameter('$1'), Parameter('$2'))
                     await self.env.cr.executemany(q_ins.get_sql(), to_insert)
                          
        if o2m_values:
            for record in self:
                for k, v in o2m_values.items():
                    await self._process_one2many(record, k, v)
        
        if binary_values:
            for record in self:
                await self._write_binary(record, binary_values)

        return True

    async def write(self, vals):
        await self.check_access_rights('write')
        await self.check_access_rule('write')
        
        keys_to_write = list(vals.keys())
        allowed_keys = await self._filter_authorized_fields('write', keys_to_write)
        if len(allowed_keys) != len(keys_to_write):
             pass # raise Exception("Security Error")

        # 1. DB Write (No Triggers)
        await self._write_db(vals.copy())
        
        # 2. Trigger Compute Logic
        self._modified(list(vals.keys()))
        await self.recompute()
        await self._notify_change('write')

        return True

    def _write_translation(self, values, lang):
        Translation = self.env['ir.translation']
        for record in self:
            for field_name, value in values.items():
                key_name = f"{self._name},{field_name}"
                # Find existing
                domain = [
                    ('name', '=', key_name),
                    ('res_id', '=', record.id),
                    ('lang', '=', lang),
                    ('type', '=', 'model')
                ]
                existing = Translation.search(domain, limit=1)
                if existing:
                    existing.write({'value': value, 'state': 'translated'})
                else:
                    Translation.create({
                        'name': key_name,
                        'res_id': record.id,
                        'lang': lang,
                        'type': 'model',
                        'src': '', 
                        'value': value,
                        'state': 'translated'
                    })
                
                # Invalidate Cache
                if (self._name, record.id, field_name) in self.env.cache:
                    del self.env.cache[(self._name, record.id, field_name)]
        
    def _write_binary(self, record, values):
        """
        Create/Update ir.attachment for these fields
        """
        Attachment = self.env['ir.attachment']
        for fname, datas in values.items():
            # Check existing
            domain = [
                ('res_model', '=', record._name),
                ('res_id', '=', record.id),
                ('name', '=', fname)
            ]
            existing = Attachment.search(domain)
            if existing:
                existing[0].write({'datas': datas})
            else:
                Attachment.create({
                    'name': fname,
                    'res_model': record._name,
                    'res_id': record.id,
                    'datas': datas,
                    'mimetype': 'application/octet-stream' # detection later
                })
            # Update cache
            self.env.cache[(record._name, record.id, fname)] = datas


    def _modified(self, fields_modified):
        """
        Mark fields dependent on 'fields_modified' as dirty.
        Propagates invalidation recursively.
        """
        if not self._triggers: return
        
        # 1. Identify direct triggers
        todo_fields = set()
        for f in fields_modified:
            if f in self._triggers:
                todo_fields.update(self._triggers[f])
                
        if not todo_fields: return
        
        # 2. Add to global compute queue
        for fname in todo_fields:
            field = self._fields[fname]
            
            # If stored, we need to recompute and write
            # If not stored, we just invalidate cache so next read fetches fresh
            if field.store:
                for rid in self.ids:
                    self.env.to_compute.add((self._name, rid, fname))
            else:
                 # Just Cache Invalidation
                 for rid in self.ids:
                     key = (self._name, rid, fname)
                     if key in self.env.cache:
                         del self.env.cache[key]
                         
    async def recompute(self):
        """
        Process the recompute queue and flush pending writes.
        """
        iteration = 0
        MAX_ITER = 100
        
        while self.env.to_compute:
            iteration += 1
            if iteration > MAX_ITER:
                 raise RecursionError("Infinite Loop in Recompute Graph")
            
            queue = list(self.env.to_compute)
            self.env.to_compute.clear() 
            
            # Group by Model+Field
            groups = {}
            for mname, rid, fname in queue:
                key = (mname, fname)
                if key not in groups: groups[key] = set()
                groups[key].add(rid)
                
            # Process Groups
            for (mname, fname), rids in groups.items():
                Model = self.env[mname]
                field = Model._fields[fname]
                records = Model.browse(list(rids))
                
                if field.compute:
                    method = getattr(records, field.compute)
                    if inspect.iscoroutinefunction(method):
                        await method()
                    else:
                        method()

        # Flush Pending Writes
        if self.env.pending_writes:
            model_writes = {}
            for (mname, rid), vals in self.env.pending_writes.items():
                if mname not in model_writes: model_writes[mname] = {}
                model_writes[mname][rid] = vals
            
            self.env.pending_writes.clear()
            
            for mname, id_vals_map in model_writes.items():
                Model = self.env[mname]
                
                # Group IDs by VALUES to batch write
                vals_to_ids = {} 
                
                for rid, vals in id_vals_map.items():
                    try:
                        # Convert to hashable key
                        # Handle basic types. Lists (M2M commands) must be handled carefully.
                        # Simple: tuple of sorted items.
                        key = tuple(sorted(vals.items()))
                        if key not in vals_to_ids: vals_to_ids[key] = []
                        vals_to_ids[key].append(rid)
                    except TypeError:
                        # Fallback for unhashable values
                        await Model.browse([rid])._write_db(vals)
                        
                for key_items, rids in vals_to_ids.items():
                    await Model.browse(rids)._write_db(dict(key_items))

    async def unlink(self):
        await self.check_access_rights('unlink')
        await self.check_access_rule('unlink')
        if not self.ids: return True
        
        from .tools.sql import SQLParams
        sql = SQLParams()
        ids_list = list(self.ids)
        placeholders = sql.add_many(ids_list)
        
        query = f'DELETE FROM "{self._table}" WHERE id IN ({placeholders})'
        await self.env.cr.execute(query, sql.get_params())
        await self._notify_change('unlink')
        return True

    async def _process_one2many(self, record, field_name, commands):
        """
        Process O2M commands:
        (0, 0, vals) -> Create
        (1, id, vals) -> Write
        (2, id) -> Delete (Unlink)
        (4, id, _) -> Link
        (6, 0, [ids]) -> Set Link
        """
        field = self._fields[field_name]
        Comodel = self.env[field.comodel_name]
        
        if commands is None: return

        for cmd in commands:
            if not isinstance(cmd, (list, tuple)): continue
            op = cmd[0]
            
            if op == 0: # Create
                vals = cmd[2]
                vals[field.inverse_name] = record.id
                await Comodel.create(vals)
            elif op == 1: # Write
                res_id = cmd[1]
                vals = cmd[2]
                await Comodel.browse([res_id]).write(vals)
            elif op == 2: # Delete
                res_id = cmd[1]
                await Comodel.browse([res_id]).unlink()
            elif op == 4: # Link
                res_id = cmd[1]
                await Comodel.browse([res_id]).write({field.inverse_name: record.id})
            elif op == 6: # Set
                ids = cmd[2]
                # Unlink others
                # Optimization needed: await Comodel.search...
                existing = await Comodel.search([(field.inverse_name, '=', record.id)])
                # write or unlink? Typically write(None)
                await existing.write({field.inverse_name: None}) 
                # Link new
                await Comodel.browse(ids).write({field.inverse_name: record.id})
    
    
    def fields_get(self, all_fields=None, attributes=None):
        """
        Return the definition of each field.
        """
        res = {}
        for name, field in self._fields.items():
            if all_fields and name not in all_fields:
                 continue
            
            info = {
                'type': field._type,
                'string': field.string,
                'required': field.required,
                'readonly': field.readonly,
                'help': field.help
            }
            if hasattr(field, 'comodel_name'):
                info['relation'] = field.comodel_name
            
            res[name] = info
        return res

    async def get_view_json_schema(self, view_id=None, view_type='form'):
        """
        Prototype: Returns standard JSON Schema + UI Schema (JSON Forms compatible).
        """
        # 1. Get Field Definitions
        fields_info = self.fields_get()
        
        # 2. Build JSON Schema (Data Structure)
        json_schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        # 3. Build UI Schema (Layout)
        ui_schema = {
            "type": "VerticalLayout",
            "elements": []
        }
        
        # Mapping Nexus Types -> JSON Schema Types
        type_map = {
            'char': 'string',
            'text': 'string', 
            'html': 'string',
            'integer': 'integer',
            'float': 'number',
            'boolean': 'boolean',
            'date': 'string', # format: date
            'datetime': 'string', # format: date-time
            'many2one': 'integer', # ID reference
            'one2many': 'array',
            'many2many': 'array',
            'selection': 'string',
            'binary': 'string' # base64
        }
        
        for fname, info in fields_info.items():
            nexus_type = info.get('type', 'char')
            json_type = type_map.get(nexus_type, 'string')
            
            prop = {
                "type": json_type,
                "title": info.get('string', fname),
                "readOnly": info.get('readonly', False)
            }
            
            if nexus_type in ('date', 'datetime'):
                prop['format'] = nexus_type
                
            if nexus_type == 'selection':
                # info['selection'] is list of tuples? or we need to fetch it?
                # fields_get usually doesn't return selection options unless asked?
                # For prototype, we skip enum values or fetch valid options.
                pass

            json_schema['properties'][fname] = prop
            
            if info.get('required'):
                json_schema['required'].append(fname)
                
            # Add to UI Schema (Simple Vertical Layout for now)
            ui_schema['elements'].append({
                "type": "Control",
                "scope": f"#/properties/{fname}",
                "label": info.get('string', fname)
            })
            
        return {
            "json_schema": json_schema,
            "ui_schema": ui_schema
        }

    async def get_view_info(self, view_id=None, view_type='form'):
        """
        Get the Architecture and Fields logic for the UI.
        """
        import xml.etree.ElementTree as ET
        
        # 1. Find View
        if view_id:
            views = self.env['ir.ui.view'].browse([view_id])
        else:
            views = await self.env['ir.ui.view'].search([
                ('model', '=', self._name),
                ('type', '=', view_type)
            ])
        
        if not views:
            return {
                'arch': {'tag': view_type, 'children': []},
                'fields': {},
                'model': self._name
            }
        
        # Primary View
        view = views[0]
        # Async Read Content
        await view.read(['arch', 'inherit_id', 'mode'])
        arch_xml = view.arch
        
        # Apply Inheritance
        extensions = await self.env['ir.ui.view'].search([
            ('inherit_id', '=', view.id),
            ('mode', '=', 'extension')
        ])
        
        if extensions:
            # Prefetch extension content
            await extensions.read(['arch'])
            for ext in extensions:
                try:
                    arch_xml = view.apply_inheritance(arch_xml, ext.arch)
                except Exception as e:
                    print(f"Failed to apply extension view {ext.id}: {e}")

        # 2. Parse XML
        try:
            root = ET.fromstring(arch_xml)
        except Exception as e:
            print(f"XML Parsing Error: {e}")
            return {'error': str(e)}
            
        field_nodes = []
        
        def node_to_dict(node):
            # Convert ElementTree node to Dict
            res = {
                'tag': node.tag,
                'attrs': node.attrib,
                'children': [node_to_dict(c) for c in node]
            }
            if node.tag == 'field':
                fname = node.attrib.get('name')
                if fname: field_nodes.append(fname)
            return res
            
        arch_json = node_to_dict(root)
        
        # 3. Get Field Meta
        fields_info = self.fields_get(all_fields=field_nodes)
        
        # 4. Extract Toolbar Actions
        # Helper to find buttons in architecture
        toolbar = {'print': [], 'action': []}
        
        # A. Recursive search for <button> in arch
        def extract_buttons(node):
            if node['tag'] == 'button':
                btn = {
                    'name': node['attrs'].get('string', node['attrs'].get('name')),
                    'type': node['attrs'].get('type', 'object'),
                    'method': node['attrs'].get('name'),
                    'modifiers': node['attrs'].get('modifiers', '{}') # TODO: Dynamic syntax
                }
                toolbar['action'].append(btn)
            
            for child in node.get('children', []):
                extract_buttons(child)
                
        # Only extract from <header> usually? 
        # For now, let's extract all so frontend decides placement, 
        # or stricly from header found in arch_json.
        # Simple scan:
        extract_buttons(arch_json)
        
        # B. Inject "Print" Actions (Simulated)
        # In a real system, query ir.actions.report
        toolbar['print'].append({
            'name': 'Print PDF',
             'type': 'ir.actions.report',
             'action_id': 'report_pdf_default' # Placeholder
        })
        
        return {
            'arch': arch_json,
            # 'arch_xml': arch_xml, # Debug
            'fields': fields_info,
            'model': self._name,
            'view_id': view.id,
            'toolbar': toolbar # Protocol Enhancement
        }

    async def _fetch_fields(self, field_names):
        if not self.ids: return
        
        # Prefetch Optimization (Vectorization)
        to_fetch = set(self.ids)
        if self._prefetch_ids:
            to_fetch.update(self._prefetch_ids)
            
        # Only fetch records that are missing at least one requested field
        final_ids = []
        for id_val in to_fetch:
            missing = False
            for fname in field_names:
                if (self._name, id_val, fname) not in self.env.cache:
                    missing = True
                    break
            if missing:
                final_ids.append(id_val)
                
        if not final_ids: return

        ids_list = list(final_ids)
        placeholders = ", ".join(["%s"] * len(ids_list))
        # Ensure we construct valid SQL with quotes
        safe_fields = [f'"{f}"' for f in field_names]
        query = f'SELECT id, {", ".join(safe_fields)} FROM "{self._table}" WHERE id IN ({placeholders})'
        
        await self.env.cr.execute(query, tuple(ids_list))
        rows = self.env.cr.fetchall()
        for row in rows:
            id_val = row[0]
            for i, fname in enumerate(field_names):
                self.env.cache[(self._name, id_val, fname)] = row[i+1]
    
    @classmethod
    async def _auto_init(cls, cr):
        cols = []
        constraints = []
        m2m_fields = []

        for name, field in cls._fields.items():
            if field._sql_type:
                if name == 'id': 
                    col_def = '"id" INTEGER PRIMARY KEY AUTOINCREMENT'
                else:
                    col_def = f'"{name}" {field._sql_type}'
                
                if isinstance(field, Many2one):
                    ref = field.comodel_name.replace('.', '_')
                    constraints.append(f'FOREIGN KEY ("{name}") REFERENCES "{ref}" (id) ON DELETE {field.ondelete.upper()}')
                cols.append(col_def)
            elif isinstance(field, Many2many):
                m2m_fields.append((name, field))

        await AsyncDatabase.create_table(cr, cls._table, cols, constraints)
        
        for name, field in m2m_fields:
            comodel = Registry.get(field.comodel_name)
            if not comodel: continue
            
            t1 = cls._table
            t2 = comodel._table
            
            if not field.relation: field.relation = f"{min(t1, t2)}_{max(t1, t2)}_rel"
            if not field.column1: field.column1 = f"{t1}_id"
            if not field.column2: field.column2 = f"{t2}_id"
            
            await AsyncDatabase.create_pivot_table(cr, field.relation, field.column1, t1, field.column2, t2)

        # Create Indexes
        for name, field in cls._fields.items():
            if getattr(field, 'index', None):
                # If index is True, default to btree
                # If index is 'gin', 'gist', etc. use it
                method = 'btree'
                if isinstance(field.index, str):
                    method = field.index
                
                await AsyncDatabase.create_index(cr, cls._table, name, method=method)

class TransientModel(Model):
    _transient = True
    
    @classmethod
    async def _auto_init(cls, cr):
        await super()._auto_init(cr)
        pass
        
    def _transient_vacuum(self, age_hours=1):
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=age_hours)
        
        query = f'DELETE FROM "{self._table}" WHERE create_date < %s'
        self.env.cr.execute(query, (cutoff,))
        print(f"Vacuum cleaned {self._name}")


class Snapshot:
    def __init__(self, record, vals):
        self._record = record
        self._values = vals.copy()
        self._changed = set()
        self.env = record.env # Copy env
        self.id = vals.get('id') or None # Virtual ID?
        
    def __getattr__(self, name):
        # 1. Check local values
        if name in self._values:
            val = self._values[name]
            # Handle O2M commands -> RecordSet-like object
            if self._record._fields[name]._type == 'one2many':
                return self._resolve_o2m_commands(name, val)
            return val
            
        # 2. Delegate to real record (Method or Field lookup)
        # Even if record is empty, we want to access methods.
        return getattr(self._record, name)
        
    def __setattr__(self, name, value):
        if name.startswith('_') or name in ('id', 'env'):
            super().__setattr__(name, value)
            return
            
        self._values[name] = value
        self._changed.add(name)

    def _resolve_o2m_commands(self, field_name, commands):
        # Convert commands to a list of Snapshot objects (virtual records)
        # (0, 0, vals) -> New snapshot
        # (1, id, vals) -> Browse(id) merged with vals
        # (2, id) -> Exclude
        # (4, id) -> Browse(id)
        
        Comodel = self.env[self._record._fields[field_name].comodel_name]
        records = []
        
        for cmd in commands:
            op = cmd[0]
            if op == 0: # New
               records.append(Snapshot(Comodel.browse([]), cmd[2]))
            elif op == 1: # Update existing
               real = Comodel.browse([cmd[1]])
               # We need to merge real + new vals
               # Complex: we need a Snapshot that falls back to real
               # But for now, let's just use vals for calculation if sufficient
               # Or create a Snapshot wrapping real record with overlay vals
               records.append(Snapshot(real, cmd[2])) 
            elif op == 4: # Link
               records.append(Snapshot(Comodel.browse([cmd[1]]), {}))
            # op 2 (delete) -> Do nothing (skip)
        
        return records
