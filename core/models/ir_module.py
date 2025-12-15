from core.orm import Model
from core.fields import Char, Selection, Text

class IrModule(Model):
    _name = 'ir.module.module'
    _description = 'Module'

    name = Char(string='Name', required=True)
    state = Char(string='State', default='uninstalled') # installed, uninstalled, to upgrade
    dependencies = Text(string='Dependencies') # JSON or comma separated
    version = Char(string='Version')
    author = Char(string='Author')
    summary = Char(string='Summary')
