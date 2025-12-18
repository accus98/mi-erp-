
import asyncio
import os
import json
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.env import Environment
from core.bus import bus
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)

# Mock Bus Broadcast
received_messages = []
original_broadcast = bus.broadcast

async def mock_broadcast(msg):
    print(f"TEST BUS: Received {msg}")
    received_messages.append(msg)
    await original_broadcast(msg)

bus.broadcast = mock_broadcast

# Mock Model
class TestRealTime(Model):
    _name = 'test.realtime'

Registry.register('test.realtime', TestRealTime)

async def run_test():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    # Create Table if needed
    async with AsyncDatabase.acquire() as cr:
        await AsyncDatabase.create_table(cr, 'test_realtime', ['id SERIAL PRIMARY KEY', 'create_date TIMESTAMP', 'write_date TIMESTAMP'], [])

    # Start Listener (Import locally to ensure it uses initialized DB?)
    # importing from core.http_fastapi might trigger app creation, side effects.
    # Let's perform a direct listen test or duplicate the listener logic here for isolation.
    # But verifying the *actual* listener code is better.
    from core.http_fastapi import pg_listener
    
    print("Starting Listener Task...")
    listener_task = asyncio.create_task(pg_listener())
    
    # Wait for connection
    await asyncio.sleep(2)
    
    # Create Record
    print("Creating Record...")
    async with AsyncDatabase.acquire() as cr:
        env = Environment(cr, uid=1, context={})
        model = TestRealTime(env)
        await model.create({'id': 999})
        # If ID auto-gen, it's fine.
        
    print("Waiting for Notification...")
    # Give it time to roundtrip via Postgres
    for i in range(10):
        if received_messages:
            break
        await asyncio.sleep(0.5)
        
    print(f"Messages Received: {len(received_messages)}")
    if len(received_messages) > 0:
        msg = received_messages[0]
        if msg['model'] == 'test.realtime' and msg['type'] == 'create':
             print("PASS: Correct Notification content")
        else:
             print(f"FAIL: Unexpected content: {msg}")
    else:
        print("FAIL: No messages received")
        
    # Cleanup
    listener_task.cancel()
    await AsyncDatabase.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        pass
