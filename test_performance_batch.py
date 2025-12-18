
import asyncio
import time
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char, Many2many
from core.env import Environment

class PerfTag(Model):
    _name = 'perf.tag'
    name = Char()

class PerfRecord(Model):
    _name = 'perf.record'
    name = Char()
    tag_ids = Many2many('perf.tag', relation='perf_record_tag_rel', column1='record_id', column2='tag_id')

Registry.register('perf.tag', PerfTag)
Registry.register('perf.record', PerfRecord)

async def test_batch():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
        await PerfTag._auto_init(cr)
        await PerfRecord._auto_init(cr)
        
        env = Environment(cr, uid=1, context={})
        
        # 1. Create Tags (Check Batch Create of Main Records)
        print("Creating 100 Tags...")
        tags_data = [{'name': f'Tag {i}'} for i in range(100)]
        start = time.time()
        tags = await env['perf.tag'].create(tags_data)
        end = time.time()
        print(f"Created {len(tags)} tags in {end - start:.4f}s")
        
        tag_ids = tags.ids
        
        # 2. Create Records with M2M (Check Batch Relation Logic)
        print("Creating 50 Records each with all 100 tags...")
        # Using raw list
        records_data = []
        for i in range(25):
            records_data.append({
                'name': f'Rec Raw {i}',
                'tag_ids': tag_ids # Raw list of 100 IDs
            })
            
        # Using Command (6, 0)
        for i in range(25):
            records_data.append({
                'name': f'Rec Cmd {i}',
                'tag_ids': [(6, 0, tag_ids)] 
            })
            
        start = time.time()
        records = await env['perf.record'].create(records_data)
        end = time.time()
        print(f"Created {len(records)} records with relations in {end - start:.4f}s")
        
        # Verify Relations
        print("Verifying Relations...")
        # Pick one raw, one cmd
        rec_raw = records[0]
        rec_cmd = records[25]
        
        # We need async access now! (Checking DX Phase 11 too)
        # Relation 'tag_ids' should return FieldFuture or RecordSet
        
        # Ensure tags loaded? 
        # Create invalidates/updates cache. 'create' returns records.
        # But create line 1033 only caches SQL fields.
        # Relations?
        # My new logic DOES NOT update cache for relations in the loop (I removed `record.write` which updated cache).
        # Oops. The new batch logic inserts into DB but DOES NOT update `env.cache`.
        # So `rec.tag_ids` will result in Cache Miss -> FieldFuture.
        # FieldFuture -> fetch from DB.
        # So it should be fine! (Correctness check).
        # Actually, `write` updates cache. My manual `executemany` bypasses cache.
        # That's acceptable for performance, as long as next read fetches correctly.
        
        tags_raw = await rec_raw.tag_ids
        print(f"Rec Raw Tags: {len(tags_raw)}")
        
        tags_cmd = await rec_cmd.tag_ids
        print(f"Rec Cmd Tags: {len(tags_cmd)}")
        
        if len(tags_raw) == 100 and len(tags_cmd) == 100:
            print("PASS: Batch Relations Created Successfully.")
        else:
            print("FAIL: Missing Relations.")

    await AsyncDatabase.close()

if __name__ == "__main__":
    asyncio.run(test_batch())
