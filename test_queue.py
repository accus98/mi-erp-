
import asyncio
import os
import json
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char, Boolean
from core.env import Environment
from core.queue import TaskQueue
from core.cache import Cache
from unittest.mock import MagicMock

# Mock Model
class QueueTest(Model):
    _name = 'queue.test'
    name = Char()
    processed = Boolean(default=False)
    
    def action_process(self, suffix):
        print(f"Executing action_process for {self.ids} with {suffix}")
        # Need to be async if we want to write? The execute_task detects coroutine.
        # But this method definition is sync.
        # Let's make it async to show full capabilities.
        return self._async_action_process(suffix)

    async def _async_action_process(self, suffix):
         await self.ensure(['name'])
         await self.write({'name': f"{self.name} {suffix}", 'processed': True})

Registry.register('queue.test', QueueTest)

# Mock Redis
class MockRedis:
    def __init__(self):
        self.queue = []
        
    def lpush(self, key, value):
        self.queue.insert(0, value)
        
    def brpop(self, key, timeout=0):
        # Simulate blocking pop
        if self.queue:
             return (key, self.queue.pop())
        return None

mock_redis = MockRedis()

async def test_queue():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    # Setup Mock
    Cache.initialized = True
    Cache.use_redis = True
    Cache.redis = mock_redis
    
    # Create Record
    async with AsyncDatabase.acquire() as cr:
        # await AsyncDatabase.create_table(cr, 'queue_test', ['id SERIAL PRIMARY KEY', 'name VARCHAR', 'processed BOOLEAN'], [])
        # Use auto_init to get all fields
        env = Environment(cr, uid=1, context={})
        q_model = QueueTest(env)
        await q_model._auto_init(cr)
        
        rec = await q_model.create({'name': 'Task'})
        rec_id = rec.id
        
    print(f"Record Created: {rec_id}")
    
    # Enqueue Task
    print("Enqueueing Task...")
    await TaskQueue.enqueue('queue.test.action_process', 'Done', uid=1, ids=[rec_id])
    # Note: Client call usually doesn't pass 'ids' in kwargs for method call on model?
    # execute_task does: model = Model(env); getattr(model, method)(*args, **kwargs)
    # The method called is bound to an empty recordset `model`. 
    # Standard Odoo/ERP way: method(ids, *args) OR model.browse(ids).method().
    # core/queue.py implementation:
    # model = Model(env) -> getattr -> execute.
    # So `action_process` receives `*args` and `**kwargs`.
    # It does NOT operate on a specific ID unless we browse inside or pass IDs.
    # My test method `action_process` behaves like a proper method on `self`.
    # BUT `model` in queue.py is `Model(env)` (empty recordset).
    # IF I want to run on specific records, I must pass IDs and browse inside, OR my queue.py should handle it.
    # Current queue.py: `method = getattr(model, method_name); await method(*args, **kwargs)`
    # So calling `action_process` on empty recordset `self`.
    # `self.ids` will be empty.
    # FIX: `action_process` needs to receive IDs?
    # Or queue logic should support `ids` payload?
    
    # Let's check logic:
    # If I pass `ids` in `kwargs`, `action_process` receives it.
    # `def action_process(self, suffix, ids=None): ...`
    # But `self` is still empty.
    
    # If I want `self` to be populated, I should update `queue.py` logic to `browse` if IDs provided?
    # OR the task name should be generic, and arguments include IDs.
    # Let's adjust test to pass IDs in kwargs, and method to inspect kwargs or args.
    # Actually, `Model` methods usually expect `self` to be set.
    # To set `self`, we need `browse`.
    # queue.py doesn't currently browse.
    
    # I will modify the queue logic in `test_queue.py` via an override? 
    # No, I should fix `queue.py` if needed.
    # Plan: keep `queue.py` generic.
    # Models should have `@classmethod` or `@api.model` equivalent if no IDs.
    # If IDs needed, the method usually takes them as first arg `def action(self, ids, ...)` (Old API)
    # New API: `self` implies IDs.
    # So we need to construct `model.browse(ids)` before calling method.
    # But queue payload structure `args, kwargs` is generic.
    # Let's update `queue.py` to check for `ids` in payload top-level?
    # Or rely on method implementation?
    
    # Let's Try:
    # `action_process` explicitly takes `ids` arg.
    # `def action_process(self, suffix, ids=None)`
    # And inside: `records = self.browse(ids)`
    
    pass

    # Actually execute
    # Manually run one cycle of worker logic to avoid infinite loop
    print("Running Worker Cycle...")
    msg = mock_redis.brpop(TaskQueue.QUEUE_KEY)
    if msg:
        _, data = msg
        payload = json.loads(data)
        # Fix execute_task call? 'model.name.method'
        # queue.py execute_task instantiates Model(env)
        # So we update Test Model to handle empty self
        await TaskQueue.execute_task(payload)
        
    # Verify result
    async with AsyncDatabase.acquire() as cr:
        env = Environment(cr, uid=1, context={})
        q_model = QueueTest(env)
        rec = await q_model.browse([rec_id]).read(['name', 'processed'])
        print(f"Result: {rec}")
        if rec[0]['processed'] and 'Done' in rec[0]['name']:
             print("PASS: Task Executed.")
        else:
             print("FAIL: Task not executed correctly.")
             
    await AsyncDatabase.close()

# Update QueueTest to handle manual browsing logic
def action_process(self, suffix, ids=None):
    # This method is what gets called on Model(env)
    if ids:
        records = self.browse(ids)
    else:
        records = self
        
    return records._async_action_process(suffix)

QueueTest.action_process = action_process

if __name__ == "__main__":
    asyncio.run(test_queue())
