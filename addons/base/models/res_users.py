from core.orm import Model
from core.fields import Char, Many2one
from core.orm import Model
from core.fields import Char, Many2one, Many2many
from core.auth import verify_password, get_password_hash

class ResUsers(Model):
    _name = 'res.users'
    _description = 'Users'

    login = Char(string="Login", required=True)
    password = Char(string="Password")
    partner_id = Many2one('res.partner', string="Related Partner")
    groups_id = Many2many('res.groups', string="Groups")
    
    company_id = Many2one('res.company', string='Company', required=False) # Make required later
    company_ids = Many2many('res.company', string='Allowed Companies')

    @classmethod
    def create(cls, env, vals): 
        # API v2 create receives 'vals' but is called on 'env[model]'.
        # However, Model.create was defined as instance method on RecordSet in `orm.py`.
        # So it receives `self` (an empty recordset).
        # We need to match signature: create(self, vals)
        pass 
        # Wait, in orm.py create(self, vals). 
        # But we are overriding it here.
        # Since we use `super().create(vals)`, we need to adapt.
        
    def create(self, vals):
        if 'password' in vals:
            vals['password'] = get_password_hash(vals['password'])
        return super().create(vals)
    
    def write(self, vals):
        if 'password' in vals:
            vals['password'] = get_password_hash(vals['password'])
        return super().write(vals)

    def _check_credentials(self, login, password):
        """
        Verifies login/password. Returns user_id or None.
        Supports automatic migration from plaintext to hash.
        """
        users = self.search([('login', '=', login)])
        if not users:
            return None
        
        user = users[0]
        stored_password = user.password # Can be plain 'admin' or hash '$2b$...'

        if not stored_password:
             return None

        # 1. Try Hash Verification (The Secure Way)
        try:
            if verify_password(password, stored_password):
                return user.id
        except ValueError:
            # Stored password is not a valid hash (likely plaintext)
            pass
        except Exception as e:
            print(f"Auth Warning: Hash verification error: {e}")

        # 2. Fallback: Plaintext Check & Auto-Migration
        if stored_password == password:
            print(f"SECURITY ALERT: User {login} using plaintext password. Migrating to Hash...", flush=True)
            
            new_hash = get_password_hash(password)
            
            # Direct SQL Update to bypass ORM loop/overhead and ensure commit
            # Using self._table requires that it is set. 
            # If we are in model context, self._table should be valid.
            table = self._table
            
            # Use raw cursor from env
            self.env.cr.execute(f'UPDATE "{table}" SET password = %s WHERE id = %s', (new_hash, user.id))
            self.env.cr.connection.commit()
            
            return user.id
        
        return None

    def get_group_ids(self):
        """
        Return list of all group IDs this user belongs to, 
        including implied groups (transitive closure).
        """
        if not self: return []
        
        # Start with direct groups
        # We use explicit SQL for performance and to avoid infinite recursion issues 
        # if the ORM tries to check access rights while computing groups.
        
        # 1. Get direct groups
        self.env.cr.execute(
            'SELECT res_groups_id FROM res_groups_res_users_rel WHERE res_users_id = %s', 
            (self.id,)
        )
        group_ids = set(row[0] for row in self.env.cr.fetchall())
        
        # 2. Expand implied groups (Breadth-First Search)
        # implied structure: res_groups_implied_rel (gid, hid) -> gid inherits hid
        # gid implies hid. If I have distinct gid, I also have hid.
        # Wait, the checking naming in res_groups.py:
        # implied_ids = Many2many('res.groups', 'res_groups_implied_rel', 'gid', 'hid', string='Inherits')
        # gid is the group that *has* the implied ids. hid is the implied group.
        # So providing gid implies having hid.
        
        to_process = list(group_ids)
        processed = set()
        
        while to_process:
            gid = to_process.pop(0)
            if gid in processed: continue
            processed.add(gid)
            
            # Find groups implied by gid
            # SELECT hid FROM res_groups_implied_rel WHERE gid = %s
            self.env.cr.execute(
                'SELECT hid FROM res_groups_implied_rel WHERE gid = %s',
                (gid,)
            )
            for row in self.env.cr.fetchall():
                implied_gid = row[0]
                if implied_gid not in group_ids:
                    group_ids.add(implied_gid)
                    to_process.append(implied_gid)
                    
        return list(group_ids)
