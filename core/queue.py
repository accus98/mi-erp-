
import json
import asyncio
from core.cache import Cache
from core.registry import Registry
from core.db_async import AsyncDatabase
from core.env import Environment
import inspect

class TaskQueue:
    QUEUE_KEY = "erp:queue:default"
    
    @classmethod
    async def enqueue(cls, task_name, *args, **kwargs):
        """
        Push task to Redis List.
        task_name: 'model.name.method'
        """
        if not Cache.initialized: Cache.initialize()
        
        payload = {
            'task': task_name,
            'args': args,
            'kwargs': kwargs
        }
        data = json.dumps(payload)
        
        if Cache.use_redis:
            # Sync redis client call
            try:
                # Use to_thread to avoid blocking loop on network I/O even if fast
                await asyncio.to_thread(Cache.redis.lpush, cls.QUEUE_KEY, data)
                print(f"Task Enqueued: {task_name}")
            except Exception as e:
                print(f"Enqueue Error: {e}")
        else:
            print("Redis unavailable. Skipping Async Task.")
            # Optional: Fallback to sync execution?
            # await cls.execute_task(payload)

    @classmethod
    async def worker(cls):
        """
        Async Worker Loop.
        """
        print("Queue Worker Started...")
        if not Cache.initialized: Cache.initialize()
        
        if not Cache.use_redis:
            print("Queue Worker: Redis not available. Worker stopping.")
            return

        while True:
            try:
                # BRPOP is blocking. Must run in thread.
                # Timeout 5 seconds
                msg = await asyncio.to_thread(Cache.redis.brpop, cls.QUEUE_KEY, 5)
                
                if msg:
                    # msg is (key, value)
                    _, data = msg
                    payload = json.loads(data)
                    await cls.execute_task(payload)
                else:
                    # Timeout reached, loop continues
                    pass
                    
            except Exception as e:
                print(f"Queue Worker Error: {e}")
                await asyncio.sleep(5)
                
    @classmethod
    async def execute_task(cls, payload):
        task_name = payload['task']
        args = payload.get('args', [])
        kwargs = payload.get('kwargs', {})
        
        print(f"Processing Task: {task_name}")
        
        try:
            # Parse 'model.name.method'
            if '.' in task_name:
                parts = task_name.split('.')
                method_name = parts[-1]
                model_name = ".".join(parts[:-1])
                
                # Check Registry
                Model = Registry.get(model_name)
                if Model:
                    async with AsyncDatabase.acquire() as cr:
                        uid = kwargs.pop('uid', 1) 
                        env = Environment(cr, uid=uid, context={})
                        model = Model(env)
                        
                        # Call method
                        if not hasattr(model, method_name):
                             print(f"Error: Method {method_name} not found on {model_name}")
                             return

                        method = getattr(model, method_name)
                        
                        res = method(*args, **kwargs)
                        if inspect.isawaitable(res):
                            await res
                            
                        print(f"Task {task_name} Completed.")
                        return

            print(f"Task Execution Failed: {task_name} not found or invalid format.")
            
        except Exception as e:
            print(f"Task Execution Exception: {e}")
            # TODO: Retry logic?
