from core.orm import Model
from core.fields import Char, Integer
import datetime

class IrSequence(Model):
    _name = 'ir.sequence'
    _description = 'Sequence'

    name = Char(string='Name', required=True)
    code = Char(string='Code', required=True) # e.g. 'sale.order'
    prefix = Char(string='Prefix') # e.g. 'SO/%(year)s/'
    padding = Integer(string='Padding', default=5)
    number_next = Integer(string='Next Number', default=1)
    number_increment = Integer(string='Increment', default=1)
    
    def next_by_code(self, code):
        """
        Get the next number for the given code.
        """
        # Search for sequence
        # We need a context or environment usually. 
        # Since this is a method on the model, 'self' is the empty recordset with env.
        
        # This acts as a static method on the model usually called via env['ir.sequence'].next_by_code('code')
        seqs = self.search([('code', '=', code)])
        if not seqs:
            return None
        
        seq = seqs[0]
        
        # 1. Calculate Prefix
        # Support %(year)s, %(month)s, %(day)s
        now = datetime.datetime.now()
        prefix = seq.prefix or ''
        try:
            prefix = prefix % {
                'year': now.year,
                'month': now.month,
                'day': now.day,
                'y': now.strftime('%y')
            }
        except:
            pass # Keep raw if format fails
            
        # 2. Format Number
        number = str(seq.number_next).zfill(int(seq.padding))
        
        # 3. Update DB
        # Use SQL update to avoid concurrency issues ideally, but ORM write is okay for MVP
        seq.write({'number_next': seq.number_next + seq.number_increment})
        
        return f"{prefix}{number}"
