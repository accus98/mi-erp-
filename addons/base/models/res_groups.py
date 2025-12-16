from core.orm import Model
from core.fields import Char, Many2many

class ResGroups(Model):
    _name = 'res.groups'
    _description = 'Access Groups'

    name = Char(string='Name', required=True)
    users = Many2many('res.users', string='Users')
    implied_ids = Many2many('res.groups', relation='res_groups_implied_rel', column1='gid', column2='hid', string='Inherits')
    
    # helper for inheritance
    def get_application_groups(self, domain=None):
        return self.search(domain or [])
