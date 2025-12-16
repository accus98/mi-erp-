from core.orm import Model
from core.fields import Char, Integer, DateTime, Float, Many2one, One2many, Selection
import datetime

class SaleOrder(Model):
    _name = 'sale.order'
    _description = 'Sales Order'

    name = Char(string='Order Reference', required=True, default='New')
    date_order = DateTime(string='Order Date')
    state = Selection(string='Status', selection=[
        ('draft', 'Quotation'),
        ('confirm', 'Confirmed'),
        ('done', 'Locked')
    ], default='draft')
    
    partner_id = Many2one('res.partner', string='Customer', required=True)
    # user_id = Many2one('res.users', string='Salesperson') # We need res.users exposed
    
    amount_total = Float(string='Total')

    lines = One2many('sale.order.line', 'order_id', string='Order Lines')

    def onchange_lines(self):
        # Calculate Total
        total = 0.0
        for line in self.lines:
            # line is a Snapshot object
            total += (line.product_uom_qty or 0.0) * (line.price_unit or 0.0)
        self.amount_total = total

    async def create(self, vals):
        if vals.get('name', 'New') == 'New':
            # Use Sequence
            seq = await self.env['ir.sequence'].next_by_code('sale.order') or 'New'
            vals['name'] = seq
            
        return await super().create(vals)

    async def action_confirm(self):
        await self.write({'state': 'confirm'})

class SaleOrderLine(Model):
    _name = 'sale.order.line'
    _description = 'Sales Order Line'
    
    order_id = Many2one('sale.order', string='Order Reference')
    name = Char(string='Description')
    product_uom_qty = Float(string='Quantity', default=1.0)
    price_unit = Float(string='Unit Price')
    price_subtotal = Float(string='Subtotal')
    
