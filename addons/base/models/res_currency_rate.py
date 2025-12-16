from core.orm import Model
from core.fields import Many2one, Date, Float, Char

class ResCurrencyRate(Model):
    _name = 'res.currency.rate'
    _description = 'Currency Rate'
    _order = 'name desc'

    currency_id = Many2one('res.currency', string='Currency', required=True, ondelete='cascade')
    name = Date(string='Date', required=True, default=lambda: Date.today()) # Need Date helper or datetime
    rate = Float(string='Rate', default=1.0)
    company_id = Many2one('res.company', string='Company')
