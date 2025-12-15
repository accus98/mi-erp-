import sys
import os
from core.orm import Model
from core.fields import Integer, Char
from core.api import depends
from core.db import Database
from core.env import Environment

# 1. Define Base Model
class SaleOrder(Model):
    _name = 'sale.order'
    name = Char(string='Order Ref')
    price = Integer(string='Price')
    qty = Integer(string='Quantity')

# 2. Define Extension (Inheritance) with Compute
class SaleOrderExtension(Model):
    _inherit = 'sale.order'
    
    total = Integer(string='Total', compute='_compute_total', store=True) # Stored compute
    
    @depends('price', 'qty')
    def _compute_total(self):
        for record in self:
            if record.price and record.qty:
                record.total = record.price * record.qty
            else:
                record.total = 0

def run_test():
    print("--- Testing Reactivity ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        SaleOrder._auto_init(cr) # Should create table with 'total' column too!
        
        env = Environment(cr, uid=1)
        Order = env['sale.order']
        
        # Create
        print("Creating Order (10 * 2)...")
        o = Order.create({'name': 'SO001', 'price': 10, 'qty': 2})
        print(f"Created ID: {o.ids}")
        print(f"Computed Total: {o.total}") # Should be 20
        
        if o.total != 20:
             print("FAILURE: Initial compute wrong.")
        else:
             print("SUCCESS: Initial compute correct.")

        # Update (Reactivity)
        print("Updating Qty to 3...")
        o.write({'qty': 3})
        
        # For stored fields, we check the value again. 
        # Since write() updates cache, o.total (via __get__) pulls from cache.
        print(f"New Total: {o.total}") # Should be 30
        
        if o.total == 30:
             print("SUCCESS: Reactivity works!")
        else:
             print(f"FAILURE: Reactivity failed. Got {o.total}")

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")

if __name__ == "__main__":
    run_test()
