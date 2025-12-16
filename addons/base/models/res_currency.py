from core.orm import Model
from core.fields import Char, Float, Boolean

class ResCurrency(Model):
    _name = 'res.currency'
    _description = 'Currency'

    name = Char(string='Currency', required=True)
    symbol = Char(string='Symbol', required=True)
    rate = Float(string='Current Rate', compute='_compute_current_rate')
    active = Boolean(string='Active', default=True)

    def _compute_current_rate(self):
        # Env context date or today
        date = self.env.context.get('date')
        if not date:
            import datetime
            date = datetime.date.today()
            
        company_id = self.env.company.id # Use Environment company
        
        for rec in self:
            # Find latest rate <= date for this currency and company
            # We need to query res.currency.rate
            # Access logic via ORM or SQL directly for performance? ORM is fine.
            
            # Domain: currency_id = rec.id AND name <= date AND (company_id = company_id OR company_id IS NULL)
            # Order: name desc, id desc (latest first)
            # Limit: 1
            
            # Note: DomainParser handles <= ? Yes, standard operator.
            
            rates = self.env['res.currency.rate'].search([
                ('currency_id', '=', rec.id),
                ('name', '<=', date),
                '|', ('company_id', '=', company_id), ('company_id', '=', None)
            ], order='name desc, id desc', limit=1)
            
            if rates:
                rec.rate = rates[0].rate
            else:
                rec.rate = 1.0 # Default fallback
