from core.orm import Model
from core.fields import Char, Text, Integer, Selection

class IrTranslation(Model):
    _name = 'ir.translation'
    _description = 'Translation'
    
    name = Char(string='Translated Name', required=True) # e.g. 'res.partner,name'
    res_id = Integer(string='Record ID', default=0)
    lang = Char(string='Language', required=True) # e.g. 'es_ES'
    type = Selection(selection=[('model', 'Model'), ('code', 'Code'), ('view', 'View')], string='Type', default='model')
    src = Text(string='Source')
    value = Text(string='Translation Value')
    module = Char(string='Module', default='base')
    state = Selection(selection=[('to_translate', 'To Translate'), ('translated', 'Translated')], string='State', default='translated')

    # Index recommendation: (type, name, res_id, lang)
