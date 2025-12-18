from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char, Many2many
import asyncio
import os

# Import Models to Ensure Registration
import core.models.ir_model
import core.models.ir_rule
import core.models.ir_model_data
import core.auth # Registers res.users and res.groups

from core.env import Environment

async def run_test():
    print("Test: Async DX Improvements")
    
    # 1. Setup
    await AsyncDatabase.initialize()
    
    # Create Environment
    async with AsyncDatabase.acquire() as cr:
        env = Environment(cr, 1, {})
        Rule = env['ir.rule']
        Model = env['ir.model']
        
        # 1. Get a Model ID
        models = await Model.search([('model', '=', 'ir.rule')])
        if not models:
             print("SKIP: ir.rule model not found in ir.model (Bootstrap needed?)")
             return
        rule_model_id = models[0].id
        
        # 2. Create Data
        # Ensure we pass list of dicts or single dict.
        # create returns recordset
        rules = await Rule.create({'name': 'Test Rule DX', 'model_id': rule_model_id})
        r1 = rules[0] # Ensure one
        
        print(f"Created Rule ID: {r1.id}")
        
        # 3. Test Uncached Field Access
        env.cache = {} 
        r_check = Rule.browse([r1.id])
        
        try:
            val = r_check.name
            print("FAIL: Uncached field access should raise error.")
        except RuntimeError as e:
            print(f"PASS: Caught expected error: {e}")
            if "await record.ensure('name')" in str(e):
                 print("PASS: Error message contains helpful hint.")
            else:
                 print("FAIL: Error message missing hint.")
    
        # 4. Test Usage of Ensure
        print("Testing ensure()...")
        await r_check.ensure('name')
        val = r_check.name
        print(f"PASS: Access after ensure: {val}")
        
        # 5. Test Uncached M2M Access (groups)
        env.cache = {}
        try:
            val = r_check.groups
            print("FAIL: Uncached M2M access should raise error.")
        except RuntimeError as e:
            print(f"PASS: Caught expected M2M error: {e}")
            if "await record.ensure('groups')" in str(e):
                 print("PASS: M2M Error message contains helpful hint.")
    
        # 6. Test Ensure M2M
        print("Testing M2M ensure()...")
        await r_check.ensure('groups')
        groups = r_check.groups
        print(f"PASS: M2M Access after ensure: {groups} (Len: {len(groups)})")
        
        # Cleanup
        await r1.unlink()

if __name__ == "__main__":
    asyncio.run(run_test())
