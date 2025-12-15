import sys
import os
from core.orm import Model
from core.fields import Integer, Char, Many2one, One2many
from core.db import Database
from core.env import Environment

# Define Models
class TestPartner(Model):
    _name = 'test.partner'
    name = Char(string='Name')
    order_ids = One2many('test.order', 'partner_id', string='Orders')

class TestOrder(Model):
    _name = 'test.order'
    name = Char(string='Order #')
    partner_id = Many2one('test.partner', string='Customer', ondelete='cascade')

def run_test():
    print("--- Testing Relations (Many2one/One2many) ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        
        # Init tables (Partner first, then Order due to FK)
        # Note: In real system, we must resolve dependency order.
        TestPartner._auto_init(cr)
        TestOrder._auto_init(cr)
        
        env = Environment(cr, uid=1)
        Partner = env['test.partner']
        Order = env['test.order']
        
        # 1. Create Partner
        p = Partner.create({'name': 'Alice'})
        print(f"Created Partner: {p.name} ({p.ids})")
        
        # 2. Create Order linked to Partner
        o = Order.create({'name': 'ORD001', 'partner_id': p.ids[0]})
        print(f"Created Order: {o.name}, Partner_ID INT: {o.partner_id.id}")
        
        # 3. Test Navigation (Meta-Magic)
        # o.partner_id should be a RecordSet of test.partner
        print(f"Navigation: Order -> Partner Name: {o.partner_id.name}")
        
        if o.partner_id.name == 'Alice':
             print("SUCCESS: Many2one Navigation works.")
        else:
             print("FAILURE: Navigation returned wrong val.")

        # 4. Test Reverse One2many (Partner -> Orders)
        # p.order_ids
        print(f"Reverse: Partner -> Orders: {p.order_ids}")
        for order in p.order_ids:
            print(f" - Found Order: {order.name}")
            
        if len(p.order_ids) > 0 and p.order_ids[0].name == 'ORD001':
             print("SUCCESS: One2many Reverse works.")
        else:
             print("FAILURE: One2many empty.")

        conn.commit()
    except Exception as e:
        print(f"Test Error: {e}")

if __name__ == "__main__":
    run_test()
