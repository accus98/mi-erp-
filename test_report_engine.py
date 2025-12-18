
import asyncio
import xml.etree.ElementTree as ET
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char
from core.env import Environment
from core.report.engine import ReportEngine
from core.models.ir_ui_view import IrUiView

# Mock Model for Data
class ResUsers(Model):
    _name = 'res.users'
    name = Char()

class ReportDoc(Model):
    _name = 'report.doc'
    name = Char()
    description = Char()

Registry.register('ir.ui.view', IrUiView)
Registry.register('res.users', ResUsers)
Registry.register('report.doc', ReportDoc)

async def test_report():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
        # Clean Start
        await cr.execute("DROP TABLE IF EXISTS report_doc CASCADE")
        await cr.execute("DROP TABLE IF EXISTS ir_ui_view CASCADE")
        await cr.execute("DROP TABLE IF EXISTS res_users CASCADE")
        
        await IrUiView._auto_init(cr)
        await ResUsers._auto_init(cr)
        await ReportDoc._auto_init(cr)
        
        env = Environment(cr, uid=1, context={})
        
        # Init User 1
        await env['res.users'].create({'name': 'Admin'})
        
        # 1. Create Base View
        base_arch = """
        <div class="report">
            <div t-foreach="docs" t-as="doc">
                <h1>Report for <span t-field="doc.name"/></h1>
                <p t-if="doc.description">Desc: <span t-field="doc.description"/></p>
                <div class="footer">Footer</div>
            </div>
        </div>
        """
        base_view = await env['ir.ui.view'].create({
            'name': 'test.report_base',
            'model': 'report.doc',
            'type': 'qweb',
            'arch': base_arch,
            'priority': 10
        })
        
        # 2. Create Extension View
        ext_arch = """
        <div t-inherit="test.report_base">
            <xpath expr="//div[@class='footer']" position="replace">
                <div class="footer">New Footer</div>
            </xpath>
            <xpath expr="//h1" position="after">
                <h2>Subtitle</h2>
            </xpath>
        </div>
        """
        # Note: XML parser in ir_ui_view handles inheritance logic. 
        # But wait, my Engine `_get_combined_arch` assumes extension views have `inherit_id` set in DB.
        # But usually 'arch' of extension contains `xpath` elements. The logic in `ir_ui_view.apply_inheritance` parses that.
        # So I must construct extension view with `inherit_id`.
        
        ext_view = await env['ir.ui.view'].create({
            'name': 'test.report_ext',
            'model': 'report.doc',
            'type': 'qweb',
            'arch': ext_arch, # This arch is just the delta
            'inherit_id': base_view.id,
            'mode': 'extension',
            'priority': 20
        })
        
        # 3. Create Data
        doc1 = await env['report.doc'].create({'name': 'Doc A', 'description': 'Desc A'})
        doc2 = await env['report.doc'].create({'name': 'Doc B', 'description': ''}) # No desc
        
        # 4. Render
        engine = ReportEngine(env)
        
        # For simplicity in my `ir_ui_view.apply_inheritance` mock (in previous file inspection),
        # it expected `xpath` elements directly under root or similar.
        # My extension arch has `<div t-inherit...>` wrapper (Standard Odoo sometimes just has `data` or roots).
        # `ir_ui_view.py` line 30 iterates root children.
        # `ext_arch` root is `div`. Children are `xpath`. So it should work.
        
        print("Rendering...")
        html = await engine.render('test.report_base', [doc1.id, doc2.id])
        
        print(f"Rendered HTML:\n{html}")
        
        # Checks
        if "Report for Doc A" in html:
            print("PASS: t-field rendered.")
        else:
            print("FAIL: t-field missing.")
            
        if "Desc: Desc A" in html:
            print("PASS: t-if (True) and t-foreach work.")
        else:
            print("FAIL: Loop/Condition logic broken.")
            
        if "Desc: Desc B" not in html:
             print("PASS: t-if (False) works.")
             
        if "New Footer" in html:
            print("PASS: Inheritance (Replace) worked.")
        else:
            print("FAIL: Footer not replaced.")
            
        if "<h2>Subtitle</h2>" in html:
            print("PASS: Inheritance (After) worked.")
        else:
             print("FAIL: Subtitle missing.")

    await AsyncDatabase.close()

if __name__ == "__main__":
    asyncio.run(test_report())
