import sys
import os

# Add current directory to path so we can import 'core'
sys.path.append(os.getcwd())

from core.orm import Model, Char, Integer, Many2one
from core.registry import Registry

print("--- Defining Models ---")

class Partner(Model):
    _name = 'res.partner'
    _description = 'Contact'

    name = Char(string="Name", required=True)
    age = Integer(string="Age")
    parent_id = Many2one('res.partner', string="Parent Company")

print(f"Partner class created: {Partner}")
print(f"Partner fields: {Partner._fields.keys()}")

print("\n--- Checking Registry ---")
model_cls = Registry.get('res.partner')
print(f"Model in Registry for 'res.partner': {model_cls}")

if model_cls == Partner:
    print("SUCCESS: Model correctly registered.")
else:
    print("FAILURE: Model not found in registry.")

print("\n--- Testing Instantiation ---")
p = Partner(name="Odoo", age=20)
print(f"Record created: {p.name}, Age: {p.age}")

print("\n--- Testing Methods ---")
Partner.create({'name': 'New Partner'})
Partner.search([('name', '=', 'Odoo')])
