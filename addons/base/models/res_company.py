from core.orm import Model
from core.fields import Char, Many2one

class ResCompany(Model):
    _name = 'res.company'
    _description = 'Company'

    name = Char(string='Company Name', required=True)
    currency_id = Many2one('res.currency', string='Currency', required=True)
    # TODO: Add parent_id for multi-level hierarchy later if needed
