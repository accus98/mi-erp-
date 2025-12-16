from core.orm import Model
from core.fields import Char, Many2one
from core.orm import Model
from core.fields import Char, Many2one
from core.auth import verify_password, get_password_hash

class ResUsers(Model):
    _name = 'res.users'
    _description = 'Users'

    login = Char(string="Login", required=True)
    password = Char(string="Password")
    partner_id = Many2one('res.partner', string="Related Partner")

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
