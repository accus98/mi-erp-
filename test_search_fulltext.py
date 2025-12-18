
import asyncio
import os
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char, Text
from core.env import Environment

# Mock Model with GIN Index
class Document(Model):
    _name = 'test.document'
    
    title = Char(string="Title", index='fulltext') # Should trigger GIN TSVector index creation
    content = Text(string="Content")

Registry.register('test.document', Document)

async def test_full_text():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    print("Running Auto Init (Should Create GIN Index)...")
    async with AsyncDatabase.acquire() as cr:
        # Drop table to force fresh init
        await cr.execute('DROP TABLE IF EXISTS "test_document"')
        await Document._auto_init(cr)
        
        # Verify Index
        await cr.execute("""
            SELECT indexname, indexdef FROM pg_indexes 
            WHERE tablename = 'test_document' AND indexname LIKE '%_idx'
        """)
        indexes = cr.fetchall()
        print("Indexes Found:", indexes)
        
        gin_found = any('to_tsvector' in idx['indexdef'].lower() for idx in indexes)
        if gin_found:
             print("PASS: GIN Index created.")
        else:
             print("FAIL: GIN Index NOT found.")
             # exit(1) # Continue to test query anyway

    print("Inserting Data...")
    async with AsyncDatabase.acquire() as cr:
        env = Environment(cr, uid=1, context={})
        doc_model = Document(env)
        
        # Insert Spanish text
        await doc_model.create([
            {'title': 'El ingenioso hidalgo Don Quijote de la Mancha', 'content': '...'},
            {'title': 'Cien años de soledad', 'content': '...'},
            {'title': 'Manual de Python Avanzado', 'content': '...'}
        ])

    print("Testing Search 'quijote' (Case Insensitive)...")
    async with AsyncDatabase.acquire() as cr:
        env = Environment(cr, uid=1, context={})
        doc_model = Document(env)
        
        # Search using implicit @@ via domain
        # The parser expects ['field', '@@', 'value']
        # 'quijote' should match 'Quijote' in Spanish config
        results = await doc_model.search([('title', '@@', 'quijote')])
        
        print(f"Docs found: {len(results)}")
        if results:
             await results.read(['title'])
             
        for r in results:
            print(f" - {r.title}")
            
        if len(results) == 1 and 'Quijote' in results[0].title:
            print("PASS: Search 'quijote' successful.")
        else:
            print("FAIL: Search 'quijote' failed.")

    print("Testing Search 'python'...")
    async with AsyncDatabase.acquire() as cr:
        env = Environment(cr, uid=1, context={})
        doc_model = Document(env)
        
        results = await doc_model.search([('title', '@@', 'python')])
        
        if results: await results.read(['title'])
        
        if len(results) == 1 and 'Python' in results[0].title:
             print("PASS: Search 'python' successful.")
        else:
             print("FAIL: Search 'python' failed.")

    await AsyncDatabase.close()

if __name__ == "__main__":
    asyncio.run(test_full_text())
