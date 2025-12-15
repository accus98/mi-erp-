from core.orm import Model
from core.fields import Char, Integer, Text

class IrAttachment(Model):
    _name = 'ir.attachment'
    _description = 'Attachments'

    name = Char(string='Name', required=True)
    res_model = Char(string='Resource Model')
    res_id = Integer(string='Resource ID')
    datas = Text(string='File Content (Base64)') # Storing blob in Text for MVP
    mimetype = Char(string='Mime Type')
