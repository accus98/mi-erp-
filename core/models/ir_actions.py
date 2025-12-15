from core.orm import Model
from core.fields import Char

class IrActionsActWindow(Model):
    _name = 'ir.actions.act_window'
    _description = 'Window Actions'

    name = Char(string='Action Name', required=True)
    res_model = Char(string='Destination Model', required=True)
    view_mode = Char(string='View Mode') # e.g. 'tree,form'
