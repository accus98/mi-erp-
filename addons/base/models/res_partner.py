from core.orm import Model
from core.fields import Char, Integer

class ResPartner(Model):
    _name = 'res.partner'
    _description = 'Partner'

    name = Char(string="Name", required=True)
    email = Char(string="Email")
    company_id = Integer(string="Company ID") # Placeholder
