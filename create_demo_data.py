from core.db import Database
from core.env import Environment
# Explicitly import models to register them
import core.models # Registers ir.* models
import addons.base.models.res_partner
import addons.sales.models.sale_order
from core.tools.xml_loader import XmlLoader
import os

def create_demo_data():
    pass # Replaced below

def create_demo_data():
    conn = Database.connect()
    cr = conn.cursor()
    env = Environment(cr, uid=1)
    
    # 1. Load Menus and Actions
    loader = XmlLoader(env)
    # Using absolute path or relative is tricky, let's assume CWD is root
    xml_path = 'addons/sales/views/sale_view.xml'
    if os.path.exists(xml_path):
        loader.load_file(xml_path, module='sales')
    else:
        print(f"Error: {xml_path} not found")
        return

    # 2. Ensure Customer
    Partner = env['res.partner']
    conn = Database.connect()
    cr = conn.cursor()
    env = Environment(cr, uid=1)
    
    # Ensure admin partner exists (usually created by base)
    # But let's create a Customer
    Partner = env['res.partner']
    Customer = Partner.create({'name': 'Cliente Demo SA'})
    
    # Create Sale Order
    Order = env['sale.order']
    new_order = Order.create({
        'name': 'SO001',
        'partner_id': Customer[0].id,
        'state': 'draft'
    })
    
    print(f"Created Demo Order: {new_order[0].id} - SO001")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_demo_data()
