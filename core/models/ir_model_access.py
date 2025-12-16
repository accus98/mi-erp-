from core.orm import Model
from core.fields import Char, Boolean, Many2one

class IrModelAccess(Model):
    _name = 'ir.model.access'
    _description = 'Model Access Rights'

    name = Char(string='Name', required=True)
    model_id = Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    group_id = Many2one('res.groups', string='Group')
    perm_read = Boolean(string='Read Access')
    perm_write = Boolean(string='Write Access')
    perm_create = Boolean(string='Create Access')
    perm_unlink = Boolean(string='Delete Access')
