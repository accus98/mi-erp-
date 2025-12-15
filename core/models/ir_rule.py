from core.orm import Model
from core.fields import Char, Boolean, Many2one, Many2many

class IrRule(Model):
    _name = 'ir.rule'
    _description = 'Record Rules'

    name = Char(string='Name', required=True)
    model_id = Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    domain_force = Char(string='Domain', help="Python domain expression, e.g. [('user_id','=',user.id)]")
    groups = Many2many('res.groups', string='Groups') # Dummy for now until res.groups exists
    active = Boolean(string='Active', default=True)
    
    perm_read = Boolean(string='Read', default=True)
    perm_write = Boolean(string='Write', default=True)
    perm_create = Boolean(string='Create', default=True)
    perm_unlink = Boolean(string='Delete', default=True)
