
import asyncio
import os
import json
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char
from core.env import Environment
import core.models.ir_ui_view # Register ir.ui.view

# Mock Model
class ViewTest(Model):
    _name = 'view.test'
    name = Char()

Registry.register('view.test', ViewTest)

async def test_metadata():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    # Mocking ir.ui.view behavior is hard without creating records
    # But get_view_info can also handle missing view (returning default).
    # However, to test toolbar extraction, we need a view with <button>.
    
    # Let's mock the internal call to `search` inside `get_view_info`?
    # Or create a real view in DB.
    
    print("Creating Test View...")
    async with AsyncDatabase.acquire() as cr:
         env = Environment(cr, uid=1, context={})
         # Ensure ir.ui.view table
         await env['ir.ui.view']._auto_init(cr)
         
         arch_xml = """
         <form>
            <header>
                <button name="action_confirm" string="Confirm" type="object"/>
                <button name="action_cancel" string="Cancel" type="object"/>
            </header>
            <sheet>
                <group>
                    <field name="name"/>
                </group>
            </sheet>
         </form>
         """
         
         view = await env['ir.ui.view'].create({
             'name': 'Test View',
             'model': 'view.test',
             'type': 'form',
             'arch': arch_xml,
             'priority': 1
         })
         
         print(f"View Created: {view.id}")
         
         test_model = ViewTest(env)
         info = await test_model.get_view_info(view_id=view.ids[0])
         
         print("Reviewing Metadata Response...")
         # print(json.dumps(info, indent=2))
         
         toolbar = info.get('toolbar')
         if not toolbar:
             print("FAIL: No toolbar in response")
             return
             
         print("Toolbar Keys:", toolbar.keys())
         
         actions = toolbar.get('action', [])
         print(f"Actions Found: {len(actions)}")
         
         names = [a['name'] for a in actions]
         print("Action Names:", names)
         
         if 'Confirm' in names and 'Cancel' in names:
             print("PASS: <header> Buttons extracted.")
         else:
             print("FAIL: Missing buttons.")
             
         prints = toolbar.get('print', [])
         if len(prints) > 0 and prints[0]['name'] == 'Print PDF':
             print("PASS: Default Reports injected.")
         else:
             print("FAIL: Reports missing.")

    await AsyncDatabase.close()

if __name__ == "__main__":
    asyncio.run(test_metadata())
