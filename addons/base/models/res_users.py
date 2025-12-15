from core.orm import Model
from core.fields import Char, Many2one
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

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
            vals['password'] = pwd_context.hash(vals['password'])
        return super().create(vals)
    
    def write(self, vals):
        if 'password' in vals:
            vals['password'] = pwd_context.hash(vals['password'])
        return super().write(vals)

    def _check_credentials(self, login, password):
        """
        Verifies login/password. Returns user_id or None.
        """
        # 1. Search user (using self.search)
        # self is a RecordSet (likely empty if called from env['res.users'])
        users = self.search([('login', '=', login)])
        if not users:
            return None
        
        user = users[0] # This is a RecordSet of 1 record
        # user.password triggers lazy load
        
        if pwd_context.verify(password, user.password):
             return user.id # user.ids[0]? Or make .id property?
             # accessing .ids[0] manually for now as .id property not in base yet (but magic field is)
             # Wait, in MagicFields we added 'id' field.
             # Field.__get__ returns value. 
             # user.id should return the ID integer.
             return user.id
        
        return None
