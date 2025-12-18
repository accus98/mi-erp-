import asyncio
from core.db_async import AsyncDatabase
from core.env import Environment

async def test_schema():
    # Load Modules
    import core.http_fastapi
    
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    async with AsyncDatabase.acquire() as conn:
        print("Connected.")
        env = Environment(conn, uid=1)
        Users = env['res.users']
        
        print("Fetching JSON Schema for res.users...")
        schema = await Users.get_view_json_schema()
        
        import json
        print(json.dumps(schema, indent=2))
        
        # Validation checks
        js = schema['json_schema']
        assert js['type'] == 'object'
        assert 'login' in js['properties']
        assert js['properties']['login']['type'] == 'string'
        
        print("\nSUCCESS: JSON Schema generated correctly.")

if __name__ == "__main__":
    try:
        asyncio.run(test_schema())
    except Exception as e:
        print(f"ERROR: {e}")
