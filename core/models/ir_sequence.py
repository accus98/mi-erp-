from core.orm import Model
from core.fields import Char, Integer, Boolean, Many2one, One2many
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
    
    company_id = Many2one('res.company', string='Company')
    use_date_range = Boolean(string='Use Date Range', default=False)
    date_range_ids = One2many('ir.sequence.date_range', inverse_name='sequence_id', string='Date Ranges')
    
    def next_by_code(self, code):
        """
        Get the next number for the given code.
        Supports multi-company and date ranges.
        """
        # 1. Filter by Company
        domain = [('code', '=', code)]
        company_id = self.env.company.id
        if company_id:
            domain.extend(['|', ('company_id', '=', company_id), ('company_id', '=', None)])
        else:
            domain.append(('company_id', '=', None))
            
        # Order by specific company first, then generic? Assumes user wants closest match.
        # But usually generic sequences serve all. 
        # If duplicated code for different companies, we pick 'company_id = user.company_id' if exists.
        
        seqs = self.search(domain)
        if not seqs:
            return None
        
        # Pick best match: prefer exact company match over None
        seq = None
        for s in seqs:
            if s.company_id.id == company_id:
                seq = s
                break
        if not seq:
            seq = seqs[0]
        
        # 2. Date Context
        ctx_date = self.env.context.get('date')
        if not ctx_date:
            now = datetime.datetime.now()
            date_val = now.date()
        else:
             # ctx_date might be string 'YYYY-MM-DD'
             if isinstance(ctx_date, str):
                 date_val = datetime.datetime.strptime(ctx_date, '%Y-%m-%d').date()
                 now = datetime.datetime.combine(date_val, datetime.datetime.min.time()) # Approx
             else:
                 date_val = ctx_date
                 now = datetime.datetime.combine(date_val, datetime.datetime.min.time())

        # 3. Handle Date Ranges
        if seq.use_date_range:
            # Find range covering date_val
            ranges = self.env['ir.sequence.date_range'].search([
                ('sequence_id', '=', seq.id),
                ('date_from', '<=', date_val),
                ('date_to', '>=', date_val)
            ], limit=1)
            
            if ranges:
                dt_range = ranges[0]
                number_next_actual = dt_range.number_next
                # Update Range
                dt_range.write({'number_next': dt_range.number_next + seq.number_increment})
                # No change to main sequence number_next
            else:
                 # No range found? Create one automatically? 
                 # Professional behavior: usually create if auto-create logic exists (e.g. yearly).
                 # For now, fallback to main sequence or error. Fallback to main.
                 number_next_actual = seq.number_next
                 seq.write({'number_next': seq.number_next + seq.number_increment})
        else:
            number_next_actual = seq.number_next
            seq.write({'number_next': seq.number_next + seq.number_increment})

        # 4. Calculate Prefix
        prefix = seq.prefix or ''
        try:
            prefix = prefix % {
                'year': now.year,
                'month': now.month,
                'day': now.day,
                'y': now.strftime('%y')
            }
        except:
            pass 
            
        # 5. Format Number
        number = str(number_next_actual).zfill(int(seq.padding))
        
        return f"{prefix}{number}"
