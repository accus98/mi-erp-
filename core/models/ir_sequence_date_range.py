from core.orm import Model
from core.fields import Date, Integer, Many2one

class IrSequenceDateRange(Model):
    _name = 'ir.sequence.date_range'
    _description = 'Sequence Date Range'

    sequence_id = Many2one('ir.sequence', string='Sequence', required=True, ondelete='cascade')
    date_from = Date(string='From', required=True)
    date_to = Date(string='To', required=True)
    number_next = Integer(string='Next Number', default=1)
