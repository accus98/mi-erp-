import asyncio
from core.controllers.main import call_kw
from core.db_async import AsyncDatabase
from core.env import Environment
from addons.base.models.res_users import ResUsers
from core.http import Response

class MockRequest:
    def __init__(self, payload):
        self.json = payload

async def test_api_validation():
    print("Testing API Validation...")
    db = AsyncDatabase()
    await db.initialize()
    
    async with db.acquire() as cr:
        # Init Models
        await ResUsers._auto_init(cr)
        env = Environment(cr, uid=1)
        
        # 1. Test Valid Create
        print("Test 1: Valid Create (Login is required)")
        payload_valid = {
            "params": {
                "model": "res.users",
                "method": "create",
                "args": [{"login": "api_valid", "password": "123"}], # Missing name is allowed? No, name is not in fields in res_users.py yet?
                # Wait, test_orm_native.py showed `ResUsers` has no `name` in _fields? 
                # Correct. So I should NOT pass name if strict schema used?
                # Or schema allows extra fields? Pydantic default ignores extras.
                # But `login` is require=True.
            }
        }
        
        res = await call_kw(MockRequest(payload_valid), env)
        if hasattr(res, 'body'):
            print(f"Valid Result: {res.body}")
            # Expect result: {result: [id]}
        else:
            print(f"Valid Result (Dict): {res}")

        # 2. Test Invalid Create (Missing Login)
        print("\nTest 2: Invalid Create (Missing Login)")
        payload_invalid = {
            "params": {
                "model": "res.users",
                "method": "create",
                "args": [{"password": "123"}] # Missing login
            }
        }
        
        res_err = await call_kw(MockRequest(payload_invalid), env)
        if hasattr(res_err, 'body'):
             body = res_err.body
        else:
             body = res_err
             
        print(f"Invalid Result: {str(body)[:200]}...")
        
        # Verify it says "Validation Error"
        if "Validation Error" in str(body):
            print("SUCCESS: Validation intercepted error.")
        else:
            print("FAILURE: Validation NOT intercepted.")

if __name__ == "__main__":
    asyncio.run(test_api_validation())
