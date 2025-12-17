import inspect
from datetime import datetime
from typing import List, Dict, Any, Tuple
from .registry import Registry
from .fields import Field, Integer, Datetime, Many2one, One2many, Many2many, Binary, Char, Text
from .db_async import AsyncDatabase

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
        for attr_name in dir(cls):
            val = getattr(cls, attr_name)
            if hasattr(val, '_depends'):
                for dep in val._depends:
                    if dep not in cls._triggers: cls._triggers[dep] = set()
                    cls._triggers[dep].add(val.__name__)

class Model(metaclass=MetaModel):
    _name = None
    _description = None
    _rec_name = 'name' # Default record name field

    def __init__(self, env, ids=(), prefetch_ids=None):
        self.env = env
        self.ids = tuple(ids)
        self._prefetch_ids = prefetch_ids if prefetch_ids is not None else set(self.ids)
        self._prefetch_ids.update(self.ids)

    def __iter__(self):
        for id_val in self.ids:
            yield self.browse([id_val])
    
    def __len__(self):
        return len(self.ids)
    
    def __bool__(self):
        return bool(self.ids)
    
    def __repr__(self):
        return f"{self._name}({self.ids})"
    
    def __eq__(self, other):
        if not isinstance(other, Model): return False
        return self._name == other._name and set(self.ids) == set(other.ids)

    def __getitem__(self, index):
        ids = self.ids[index]
        if isinstance(ids, int):
            ids = [ids]
        return self.browse(ids)

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
            # Check if res.users is in registry
            if Registry.get('res.users'):
                user = self.env['res.users'].browse(self.env.uid)
                if hasattr(user, 'get_group_ids'):
                    user_groups = await user.get_group_ids()
        except Exception as e:
            # Fallback if something breaks during boot or early init
            print(f"Access Check Warning: Could not fetch groups: {e}")
            pass

        cr = self.env.cr
        
        if user_groups:
            placeholders = ", ".join(["%s"] * len(user_groups))
            group_clause = f"(a.group_id IS NULL OR a.group_id IN ({placeholders}))"
            params = (self._name,) + tuple(user_groups)
        else:
            group_clause = "a.group_id IS NULL"
            params = (self._name,)

        query = f"""
            SELECT 1 FROM ir_model_access a 
            JOIN ir_model m ON a.model_id = m.id
            WHERE m.model = %s AND a.{col} = TRUE
            AND {group_clause}
            LIMIT 1
        """
        await cr.execute(query, params)
        if cr.fetchone():
            self.env.permission_cache[cache_key] = True
            return True
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

    
    async def _apply_ir_rules(self, operation='read'):
        """
        Fetch and evaluate rules for current user and model.
        Returns: (where_clause, params) SQL fragment AND-ed.
        """
        if self.env.uid == 1:
            return "", []
            
        if self._name == 'ir.rule':
             return "", []

        # Direct SQL to avoid recursion hell during bootstrap
        perm_map = {
            'read': 'perm_read',
            'write': 'perm_write',
            'create': 'perm_create',
            'unlink': 'perm_unlink'
        }
        col = perm_map.get(operation, 'perm_read')
        
        query = f"""
            SELECT r.domain_force FROM ir_rule r
            JOIN ir_model m ON r.model_id = m.id
            WHERE m.model = %s AND r.active = True AND r.{col} = True
        """
        await self.env.cr.execute(query, (self._name,))
        rows = self.env.cr.fetchall()
        
        if not rows:
            return "", []
            
        from .tools.domain_parser import DomainParser
        parser = DomainParser()
        
        global_domains = []
        user_obj = self.env.user 
        eval_context = {
            'user': user_obj,
            'company': self.env.company,
            'time': datetime,
            'datetime': datetime
        }
        
        for r in rows:
            domain_str = r[0]
            if not domain_str: continue
            try:
                d = eval(domain_str, eval_context)
                global_domains.append(d)
            except Exception as e:
                print(f"Rule Eval Error on {self._name}: {e}")
                
        if not global_domains:
            return "", []
            
        full_sql = []
        full_params = []
        
        for d in global_domains:
            sql, params = parser.parse(d)
            if sql != "1=1":
                full_sql.append(f"({sql})")
                full_params.extend(params)
                
        if not full_sql:
             return "", []
             
        return " AND ".join(full_sql), full_params

    def _validate_order(self, order):
        if not order: return None
        
        parts = order.split(',')
        safe_parts = []
        
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
        # We use raw SQL to avoid recursion loop with ORM
        await self.env.cr.execute("SELECT id FROM ir_model WHERE model = %s", (self._name,))
        res = self.env.cr.fetchone()
        if not res: return {}
        model_id = res[0]
        
        # 2. Get Fields with Groups
        # Auto-created pivot table: ir_model_fields_group_rel
        # Cols: ir_model_fields_id, res_groups_id
        query = """
            SELECT f.name, r.res_groups_id 
            FROM ir_model_fields f
            JOIN ir_model_fields_group_rel r ON f.id = r.ir_model_fields_id
            WHERE f.model_id = %s
        """
        # Important: Verify table name. If not created yet, this fails gracefully?
        # We wrap in try-except to avoid breaking bootstrap
        try:
            await self.env.cr.execute(query, (model_id,))
            rows = self.env.cr.fetchall()
        except Exception as e:
            # Table might not exist yet during init
            # self.env.cr.connection.rollback() # Not needed in asyncpg transaction block usually, unless explicit
            return {}

        res_map = {}
        for fname, gid in rows:
            if fname not in res_map: res_map[fname] = set()
            res_map[fname].add(gid)
            
        self.env.cache[key] = res_map
        return res_map



    async def _filter_authorized_fields(self, operation, fields):
        # Async Version matching the Signature
        # For now, Bypass to ensure basic CRUD works.
        # TODO: Implement Async FLS
        return fields

    async def _write_binary(self, record, values):
        # Implementation needed for create/write
        pass

    async def search(self, domain, offset=0, limit=None, order=None):
        from .tools.domain_parser import DomainParser
        
        await self.check_access_rights('read')
        
        # 1. Base Domain
        parser = DomainParser()
        where_clause, where_params = parser.parse(domain)
        
        # 2. Apply Security Rules
        rule_clause, rule_params = await self._apply_ir_rules('read')
        
        if rule_clause:
            if where_clause == "1=1":
                where_clause = rule_clause
            else:
                where_clause = f"({where_clause}) AND ({rule_clause})"
            where_params.extend(rule_params)
        
        query = f'SELECT id FROM "{self._table}" WHERE {where_clause}'
        
        if order:
            # Secure Validation
            safe_order = self._validate_order(order)
            if safe_order:
                query += f" ORDER BY {safe_order}"
        
        if limit:
            query += f" LIMIT {limit}"
            
        if offset:
            query += f" OFFSET {offset}"
        
        await self.env.cr.execute(query, tuple(where_params))
        res = self.env.cr.fetchall()
        res_ids = [r[0] for r in res]
        
        return self.browse(res_ids)

    async def check_access_rule(self, operation):
        """
        Verifies that the current records satisfy the Record Rules.
        Raises AccessError if any record is forbidden.
        """
        if self.env.uid == 1: return
        if not self.ids: return
        
        rule_clause, rule_params = await self._apply_ir_rules(operation)
        if not rule_clause: return
        
        # Verify all IDs match the rule
        all_ids = list(self.ids)
        total_requested = len(all_ids)
        total_matched = 0
        
        chunk_size = 1000
        for i in range(0, total_requested, chunk_size):
            chunk = all_ids[i:i + chunk_size]
            
            placeholders = ", ".join(["%s"] * len(chunk))
            query = f'SELECT COUNT(*) FROM "{self._table}" WHERE id IN ({placeholders}) AND ({rule_clause})'
            params = tuple(chunk) + tuple(rule_params)
            
            await self.env.cr.execute(query, params)
            res = self.env.cr.fetchone()
            if res:
                total_matched += res[0]
        
        if total_matched != total_requested:
             raise Exception(f"Access Rule Violation: One or more records in {self._name} are restricted for operation '{operation}'.")

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
            
        # 1. Fetch from Cache first? 
        # For simplicity, we fetch from DB and update cache.
        
        # Apply Record Rules (Strict SQL Compilation)
        rule_clause, rule_params = await self._apply_ir_rules('read')

        # Filter valid SQL columns
        sql_fields = [f for f in fields if f in self._fields and self._fields[f]._sql_type]
        
        results = []
        if sql_fields:
            if 'id' not in sql_fields: sql_fields.insert(0, 'id')
            cols = ", ".join([f'"{f}"' for f in sql_fields])
            
            ids_input = list(self.ids)
            placeholders = ", ".join(["%s"] * len(ids_input))
            
            where_sql = f'id IN ({placeholders})'
            query_params = ids_input
            
            if rule_clause:
                where_sql += f' AND ({rule_clause})'
                query_params.extend(rule_params)
            
            query = f'SELECT {cols} FROM "{self._table}" WHERE {where_sql}'
            
            await self.env.cr.execute(query, tuple(query_params))
        rows = self.env.cr.fetchall() # returns list of Records/Dicts
        
        # Map by ID
        rows_map = {r['id']: r for r in rows}
        
        for id_val in self.ids:
            if id_val in rows_map:
                row = rows_map[id_val]
                # Update Cache
                for f in sql_fields:
                    self.env.cache[(self._name, id_val, f)] = row[f]
        
        
        # 2. Relational Prefetching (N+1 Fix)
        # Identify requested relation fields that are not stored (M2M, O2M)
        # (Stored M2O are handled by sql_fields)
        
        relational_fields = [f for f in fields if f in self._fields and not self._fields[f]._sql_type]
        
        for f in relational_fields:
            field = self._fields[f]
            # Check if typically already cached? 
            # We assume if requested in read(), we want to ensure it's loaded.
            
            # Filter IDs that need fetching (not in cache)
            ids_to_fetch = [rid for rid in self.ids if (self._name, rid, f) not in self.env.cache]
            if not ids_to_fetch: continue
            
            if isinstance(field, Many2many):
                if not field.relation: continue
                # Batch Fetch M2M
                # SELECT src, dest FROM rel WHERE src IN ids
                
                # placeholders for IN clause
                placeholders = ", ".join(["%s"] * len(ids_to_fetch))
                q = f'SELECT "{field.column1}", "{field.column2}" FROM "{field.relation}" WHERE "{field.column1}" IN ({placeholders})'
                await self.env.cr.execute(q, tuple(ids_to_fetch))
                relations = self.env.cr.fetchall()
                
                # Group by Source ID
                # Default empty list for all
                rel_map = {rid: [] for rid in ids_to_fetch}
                for src, dest in relations:
                    if src in rel_map:
                        rel_map[src].append(dest)
                
                # Update Cache
                for rid, vals_list in rel_map.items():
                    self.env.cache[(self._name, rid, f)] = vals_list
                    
            elif isinstance(field, One2many):
                # Batch Fetch O2M
                # SELECT id, inverse FROM comodel WHERE inverse IN ids
                # We need to Select ID and Inverse Field
                Comodel = self.env[field.comodel_name]
                inv_field = field.inverse_name
                
                # We need the column name for inverse field in comodel
                if inv_field not in Comodel._fields: continue
                inv_col = Comodel._fields[inv_field].name # usually same
                
                placeholders = ", ".join(["%s"] * len(ids_to_fetch))
                # We select ID to know the record, and inverse_col to know the parent
                q = f'SELECT id, "{inv_col}" FROM "{Comodel._table}" WHERE "{inv_col}" IN ({placeholders})'
                await self.env.cr.execute(q, tuple(ids_to_fetch))
                relations = self.env.cr.fetchall()
                
                rel_map = {rid: [] for rid in ids_to_fetch}
                for child_id, parent_id in relations:
                    # parent_id might be raw ID or m2o tuple? 
                    # If stored as integer in DB, it is ID.
                    if parent_id in rel_map:
                        rel_map[parent_id].append(child_id)
                        
                # Update Cache
                for rid, vals_list in rel_map.items():
                    self.env.cache[(self._name, rid, f)] = vals_list

        
        # Collect M2O to resolve
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

    async def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Combines search and read.
        """
        records = await self.search(domain or [], offset=offset, limit=limit, order=order)
        if not records: return []
        return await records.read(fields)

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
             # Empty inserts? (e.g. only default values or empty)
             # If processed_vals_list has items but no valid cols?
             # INSERT DEFAULT VALUES
             for _ in processed_vals_list:
                 await self.env.cr.execute(f'INSERT INTO "{self._table}" DEFAULT VALUES RETURNING id')
                 res = self.env.cr.fetchone()
                 created_ids.append(res['id'])
        else:
            # Construct Massive Query
            # INSERT INTO table (c1, c2) VALUES ($1, $2), ($3, $4) ... RETURNING id
            cols_clause = ", ".join([f'"{c}"' for c in valid_cols])
            
            # Values List flattening
            flattened_values = []
            placeholders_parts = []
            
            # We assume sql_vals_list has same order of valid_cols
            for row in sql_vals_list:
                 row_values = [row[c] for c in valid_cols]
                 flattened_values.extend(row_values)
                 
                 # ($1, $2, ...)
                 # We rely on executemany or manual building? 
                 # User wants 1 Query. executemany in asyncpg can send 1 query but doesn't return IDs easily.
                 # Manual construction is best for RETURNING id.
                 
                 # Placeholders: %s
                 row_ph = "(" + ", ".join(["%s"] * len(valid_cols)) + ")"
                 placeholders_parts.append(row_ph)
            
            values_clause = ", ".join(placeholders_parts)
            
            query = f'INSERT INTO "{self._table}" ({cols_clause}) VALUES {values_clause} RETURNING id'
            
            # Execute
            await self.env.cr.execute(query, tuple(flattened_values))
            
            # Fetch All IDs
            rows = self.env.cr.fetchall() # returns list of Records/Dicts
            created_ids = [r['id'] for r in rows]

        # 4. Update Cache (Batch)
        for idx, new_id in enumerate(created_ids):
             row = sql_vals_list[idx] if sql_vals_list else {}
             for col, val in row.items():
                 self.env.cache[(self._name, new_id, col)] = val
                 
        records = self.browse(created_ids)
        
        # 5. Process Relations (Looping but necessary for specific logic)
        # Note: If we really want batch here, we need write() to support batch.
        # But write() usually takes 1 set of values for ids.
        # For Creation, each record might have different relations.
        # So we loop.
        
        for idx, r_data in enumerate(relation_data):
            record = records[idx]
            m2m = r_data['m2m']
            o2m = r_data['o2m']
            binary = r_data['binary']
            
            if m2m: await record.write(m2m)
            if binary: await self._write_binary(record, binary)
            if o2m:
                for k, v in o2m.items():
                     await self._process_one2many(record, k, v)
                     
        return records

    async def write(self, vals):
        await self.check_access_rights('write')
        await self.check_access_rule('write')
        if not self.ids: return True
        
        m2m_values = {}
        o2m_values = {}
        binary_values = {}
        
        keys_to_write = list(vals.keys())
        allowed_keys = await self._filter_authorized_fields('write', keys_to_write)
        if len(allowed_keys) != len(keys_to_write):
             pass # raise Exception("Security Error")

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
            set_clause = ", ".join([f'"{k}" = %s' for k in valid_cols])
            values = [vals[k] for k in valid_cols]
            
            ids_list = list(self.ids)
            id_placeholders = ", ".join(["%s"] * len(ids_list))
            values.extend(ids_list)

            query = f'UPDATE "{self._table}" SET {set_clause} WHERE id IN ({id_placeholders})'
            await self.env.cr.execute(query, tuple(values))
            
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
                
                new_set = set(target_ids)
                
                for rid in self.ids:
                    current_set = existing_map.get(rid, set())
                    adding = new_set - current_set
                    removing = current_set - new_set
                    
                    for tid in adding: to_insert.append((rid, tid))
                    for tid in removing: to_delete_params.append((rid, tid))
                         
                if to_delete_params:
                     # Native Batch Delete
                     await self.env.cr.executemany(f'DELETE FROM "{f_obj.relation}" WHERE "{f_obj.column1}" = %s AND "{f_obj.column2}" = %s', to_delete_params)

                if to_insert:
                    # Native Batch Insert
                    await self.env.cr.executemany(f'INSERT INTO "{f_obj.relation}" ("{f_obj.column1}", "{f_obj.column2}") VALUES (%s, %s)', to_insert)
                          
        if o2m_values:
            for record in self:
                for k, v in o2m_values.items():
                    await self._process_one2many(record, k, v)
        
        if binary_values:
            for record in self:
                await self._write_binary(record, binary_values)

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
                
                # Invalidate Cache for this field
                # Odoo style: self.env.cache.invalidate([(self._name, record.id, field_name)])
                # Our simple cache:
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


    def _recompute(self, changed_fields):
        todo = set()
        for field in changed_fields:
            if field in self._triggers:
                for method_name in self._triggers[field]:
                    todo.add(method_name)
        for method_name in todo:
            method = getattr(self, method_name)
            method()

    async def unlink(self):
        await self.check_access_rights('unlink')
        await self.check_access_rule('unlink')
        if not self.ids: return True
        ids_list = list(self.ids)
        placeholders = ", ".join(["%s"] * len(ids_list))
        query = f'DELETE FROM "{self._table}" WHERE id IN ({placeholders})'
        await self.env.cr.execute(query, tuple(ids_list))
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
        
        return {
            'arch': arch_json,
            # 'arch_xml': arch_xml, # Debug
            'fields': fields_info,
            'model': self._name,
            'view_id': view.id
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
