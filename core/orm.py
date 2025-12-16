import inspect
from datetime import datetime
from typing import List, Dict, Any, Tuple
from .registry import Registry
from .fields import Field, Integer, Datetime, Many2one, One2many, Many2many, Binary, Char, Text
from .db import Database

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

    def mapped(self, field_name):
        """
        Return list of values.
        If field is relational, return recordset.
        """
        res = []
        for rec in self:
            # TODO: Improve vectorization here?
            # Accessing rec.field triggers fetch.
            # If fetch uses prefetch_ids, this is efficient.
            val = getattr(rec, field_name)
            res.append(val)
        return res

    def browse(self, ids):
        if isinstance(ids, int): ids = [ids]
        return self.env.get(self._name)._with_ids(ids, self._prefetch_ids)

    def _with_ids(self, ids, prefetch_ids=None):
        return self.__class__(self.env, tuple(ids), prefetch_ids)



    
    def check_access_rights(self, operation):
        """
        Verify access rights using ir.model.access.
        operation: 'read', 'write', 'create', 'unlink'
        """
        if self.env.uid == 1: 
            return True
        
        if self._name.startswith('ir.'):
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
                    user_groups = user.get_group_ids()
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
        cr.execute(query, params)
        if cr.fetchone():
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

    
    def _apply_ir_rules(self, operation='read'):
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
        self.env.cr.execute(query, (self._name,))
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

    def search(self, domain, offset=0, limit=None, order=None):
        from .tools.domain_parser import DomainParser
        
        self.check_access_rights('read')
        
        # 1. Base Domain
        parser = DomainParser()
        where_clause, where_params = parser.parse(domain)
        
        # 2. Apply Security Rules
        rule_clause, rule_params = self._apply_ir_rules('read')
        
        if rule_clause:
            if where_clause == "1=1":
                where_clause = rule_clause
            else:
                where_clause = f"({where_clause}) AND ({rule_clause})"
            where_params.extend(rule_params)
        
        query = f'SELECT id FROM "{self._table}" WHERE {where_clause}'
        
        if order:
            # Basic sanitization for order (very naive)
            # e.g. "name asc, id desc"
            query += f" ORDER BY {order}"
        
        if limit:
            query += f" LIMIT {limit}"
            
        if offset:
            query += f" OFFSET {offset}"
        
        # DEBUG TRACE
        print(f"DEBUG_TRACE: search SQL: {query} | Params: {where_params}", flush=True)

        self.env.cr.execute(query, tuple(where_params))
        res_ids = [r[0] for r in self.env.cr.fetchall()]
        
        # DEBUG TRACE
        print(f"DEBUG_TRACE: search Found {len(res_ids)} records for {self._name}", flush=True)

        return self.browse(res_ids)

    def check_access_rule(self, operation):
        """
        Verifies that the current records satisfy the Record Rules.
        Raises AccessError if any record is forbidden.
        """
        if self.env.uid == 1: return
        if not self.ids: return
        
        rule_clause, rule_params = self._apply_ir_rules(operation)
        if not rule_clause: return
        
        # Verify all IDs match the rule
        ids_list = list(self.ids)
        placeholders = ", ".join(["%s"] * len(ids_list))
        
        # We need to count how many of the requested IDs match the rule
        query = f'SELECT COUNT(*) FROM "{self._table}" WHERE id IN ({placeholders}) AND ({rule_clause})'
        params = tuple(ids_list) + tuple(rule_params)
        
        self.env.cr.execute(query, params)
        matched_count = self.env.cr.fetchone()[0]
        
        if matched_count != len(self.ids):
             raise Exception(f"Access Rule Violation: One or more records in {self._name} are restricted for operation '{operation}'.")

    def read(self, fields=None):
        """
        Serializes records to a list of dictionaries.
        """
        self.check_access_rights('read')
        self.check_access_rule('read')
        if not self.ids: return []
        
        res = []
        if not fields:
            fields = list(self._fields.keys())
            
        # BULK PREFETCH TRANSLATIONS
        lang = self.env.context.get('lang')
        if lang and lang != 'en_US':
             trans_fields = [f for f in fields if f in self._fields and getattr(self._fields[f], 'translate', False)]
             if trans_fields:
                  names = [f"{self._name},{f}" for f in trans_fields]
                  # Avoid potential query size issues with huge IDs lists, but fine for now
                  if self.ids:
                      ids_tuple = tuple(self.ids)
                      names_tuple = tuple(names)
                      
                      # Handle single item tuple formatting for syntax
                      ids_placeholder = ",".join(["%s"] * len(ids_tuple))
                      names_placeholder = ",".join(["%s"] * len(names_tuple))
                      
                      query = f"""
                        SELECT res_id, name, value 
                        FROM ir_translation 
                        WHERE res_id IN ({ids_placeholder}) 
                          AND name IN ({names_placeholder}) 
                          AND lang = %s
                      """
                      params = ids_tuple + names_tuple + (lang,)
                      
                      self.env.cr.execute(query, params)
                      rows = self.env.cr.fetchall()
                      
                      for r_id, r_name, r_value in rows:
                          # name format: "model_name,field_name"
                          f_name = r_name.split(',')[1] 
                          key_trans = (self._name, r_id, f_name, lang)
                          self.env.cache[key_trans] = r_value

        for record in self:
            vals = {'id': record.id}
            for fname in fields:
                if fname == 'id': continue
                if fname not in self._fields: continue
                
                field = self._fields[fname]
                val = getattr(record, fname)
                
                # Format value based on type
                if isinstance(field, Many2one):
                    # Odoo returns (id, name)
                    if val:
                        # Safe access to display_name or rec_name
                        name = getattr(val, 'display_name', None) or getattr(val, 'rec_name', None) or getattr(val, 'name', 'Unknown')
                        vals[fname] = (val.id, name)
                    else:
                        vals[fname] = False
                elif isinstance(field, (One2many, Many2many)):
                    # Odoo returns list of ids
                    vals[fname] = val.ids
                elif isinstance(field, (Datetime,)):
                    # Serialize datetime
                    if val: vals[fname] = str(val)
                    else: vals[fname] = False
                else:
                    vals[fname] = val
            res.append(vals)
        return res

    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """
        Combines search and read.
        """
        records = self.search(domain or [], offset=offset, limit=limit, order=order)
        if not records: return []
        return records.read(fields)

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



    def create(self, vals):
        self.check_access_rights('create')
        # Create does not check record rules because record doesn't exist yet.
        # But if we limit creation based on properties? 
        # Odoo checks rule AFTER creation usually (can_create logic).
        # We skip for now.
        
        # Handle defaults
        for fname, field in self._fields.items():
            if fname not in vals and hasattr(field, 'default'):
                 val = field.default
                 if callable(val): vals[fname] = val()
                 else: vals[fname] = val

        vals['create_date'] = datetime.now()
        vals['write_date'] = datetime.now()
        
        m2m_values = {}
        o2m_values = {}
        binary_values = {}
        
        for k, v in list(vals.items()):
            if k in self._fields:
                field = self._fields[k]
                if isinstance(field, Many2many):
                    m2m_values[k] = vals.pop(k)
                elif isinstance(field, One2many):
                    o2m_values[k] = vals.pop(k)
                elif isinstance(field, Binary):
                    binary_values[k] = vals.pop(k)

        if 'id' in vals and vals['id'] is None:
            del vals['id']

        valid_cols = [k for k in vals if k in self._fields and self._fields[k]._sql_type]
        cols_sql = ", ".join([f'"{k}"' for k in valid_cols])
        placeholders = ", ".join(["%s"] * len(valid_cols))
        values = [vals[k] for k in valid_cols]

        query = f'INSERT INTO "{self._table}" ({cols_sql}) VALUES ({placeholders}) RETURNING id'
        self.env.cr.execute(query, tuple(values))
        
        # Postgres returns the ID
        res = self.env.cr.fetchone()
        new_id = res[0] if res else None
        
        for k, v in vals.items():
            self.env.cache[(self._name, new_id, k)] = v
        
        # Post-process
        record = self.browse([new_id])
        
        if m2m_values:
            record.write(m2m_values)
            
        if o2m_values:
            for k, v in o2m_values.items():
                self._process_one2many(record, k, v)
            
        if binary_values:
            self._write_binary(record, binary_values)

        record._recompute(vals.keys())
        return record

    def write(self, vals):
        self.check_access_rights('write')
        self.check_access_rule('write')
        if not self.ids: return True
        
        m2m_values = {}
        o2m_values = {}
        binary_values = {}
        
        translation_values = {}
        
        lang = self.env.context.get('lang')
        is_translation_write = lang and lang != 'en_US'

        for k, v in list(vals.items()):
            if k in self._fields:
                field = self._fields[k]
                if isinstance(field, Many2many):
                    m2m_values[k] = vals.pop(k)
                elif isinstance(field, One2many):
                    o2m_values[k] = vals.pop(k)
                elif isinstance(field, Binary):
                    binary_values[k] = vals.pop(k)
                elif getattr(field, 'translate', False) and is_translation_write:
                    translation_values[k] = vals.pop(k)

        vals['write_date'] = datetime.now()
        valid_cols = [k for k in vals if k in self._fields and self._fields[k]._sql_type]
        
        if valid_cols:
            set_clause = ", ".join([f'"{k}" = %s' for k in valid_cols])
            values = [vals[k] for k in valid_cols]
            
            ids_list = list(self.ids)
            id_placeholders = ", ".join(["%s"] * len(ids_list))
            values.extend(ids_list)

            query = f'UPDATE "{self._table}" SET {set_clause} WHERE id IN ({id_placeholders})'
            self.env.cr.execute(query, tuple(values))
            
            for id_val in self.ids:
                for k, v in vals.items():
                    self.env.cache[(self._name, id_val, k)] = v
        
        if m2m_values:
            for field, target_ids in m2m_values.items():
                f_obj = self._fields[field]
                q_del = f'DELETE FROM "{f_obj.relation}" WHERE "{f_obj.column1}" = ANY(%s)'
                self.env.cr.execute(q_del, (list(self.ids),))
                
                if target_ids:
                    values_list = []
                    for r_id in self.ids:
                        for t_id in target_ids:
                            values_list.append((r_id, t_id))
                    if values_list:
                         args_str = ','.join(self.env.cr.mogrify("(%s,%s)", x).decode('utf-8') for x in values_list)
                         self.env.cr.execute(f'INSERT INTO "{f_obj.relation}" ("{f_obj.column1}", "{f_obj.column2}") VALUES ' + args_str)
                         
        if o2m_values:
            for record in self:
                for k, v in o2m_values.items():
                    self._process_one2many(record, k, v)
        
        if binary_values:
            for record in self:
                self._write_binary(record, binary_values)

        if translation_values:
             self._write_translation(translation_values, lang)

        all_changed = list(vals.keys()) + list(m2m_values.keys()) + list(o2m_values.keys()) + list(binary_values.keys()) + list(translation_values.keys())
        self._recompute(all_changed)
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

    def unlink(self):
        self.check_access_rights('unlink')
        self.check_access_rule('unlink')
        if not self.ids: return True
        ids_list = list(self.ids)
        placeholders = ", ".join(["%s"] * len(ids_list))
        query = f'DELETE FROM "{self._table}" WHERE id IN ({placeholders})'
        self.env.cr.execute(query, tuple(ids_list))
        return True
    
    
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

    def get_view_info(self, view_id=None, view_type='form'):
        """
        Get the Architecture and Fields logic for the UI.
        """
        import xml.etree.ElementTree as ET
        
        # 1. Find View
        if view_id:
            views = self.env['ir.ui.view'].browse([view_id])
        else:
            views = self.env['ir.ui.view'].search([
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
        arch_xml = view.arch
        
        # Apply Inheritance
        extensions = self.env['ir.ui.view'].search([
            ('inherit_id', '=', view.id),
            ('mode', '=', 'extension')
        ])
        
        if extensions:
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

    def _fetch_fields(self, field_names):
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
        query = f'SELECT id, {", ".join(field_names)} FROM "{self._table}" WHERE id IN ({placeholders})'
        self.env.cr.execute(query, tuple(ids_list))
        rows = self.env.cr.fetchall()
        for row in rows:
            id_val = row[0]
            for i, fname in enumerate(field_names):
                self.env.cache[(self._name, id_val, fname)] = row[i+1]
    
    @classmethod
    def _auto_init(cls, cr):
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

        Database.create_table(cr, cls._table, cols, constraints)
        
        for name, field in m2m_fields:
            comodel = Registry.get(field.comodel_name)
            if not comodel: continue
            
            t1 = cls._table
            t2 = comodel._table
            
            if not field.relation: field.relation = f"{min(t1, t2)}_{max(t1, t2)}_rel"
            if not field.column1: field.column1 = f"{t1}_id"
            if not field.column2: field.column2 = f"{t2}_id"
            
            Database.create_pivot_table(cr, field.relation, field.column1, t1, field.column2, t2)

class TransientModel(Model):
    _transient = True
    
    @classmethod
    def _auto_init(cls, cr):
        super()._auto_init(cr)
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
