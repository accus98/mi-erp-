from core.orm import Model
from core.fields import Char, Boolean, Selection

class ResLang(Model):
    _name = 'res.lang'
    _description = 'Languages'
    
    name = Char(string='Name', required=True)
    code = Char(string='Locale Code', required=True) # e.g. en_US, es_ES
    iso_code = Char(string='ISO Code') # e.g. en, es
    direction = Selection(selection=[('ltr', 'Left-to-Right'), ('rtl', 'Right-to-Left')], string='Direction', default='ltr')
    date_format = Char(string='Date Format', default='%Y-%m-%d')
    active = Boolean(string='Active', default=True)
