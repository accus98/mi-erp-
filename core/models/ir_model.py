from core.orm import Model
from core.fields import Char, Boolean, Many2one, Integer

class IrModel(Model):
    _name = 'ir.model'
    _description = 'Models'
    
    name = Char(string='Model Description', required=True)
    model = Char(string='Model Name', required=True) # e.g. 'res.partner'
    transient = Boolean(string='Transient Model')
    # One2many to fields? 
    # field_ids = One2many('ir.model.fields', 'model_id', string='Fields') 

class IrModelFields(Model):
    _name = 'ir.model.fields'
    _description = 'Fields'
    
    model_id = Many2one('ir.model', string='Model', required=True, ondelete='cascade')
    name = Char(string='Field Name', required=True)
    ttype = Char(string='Field Type', required=True)
    relation = Char(string='Related Model') # For m2o, o2m, m2m
    required = Boolean(string='Required')
    readonly = Boolean(string='Readonly')
    string = Char(string='Label')
