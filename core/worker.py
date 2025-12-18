import sys
import os
import asyncio

# Add root directory to python path
sys.path.append(os.getcwd())

from core.logger import logger
from core.db_async import AsyncDatabase
from core.models.ir_cron import IrCron
from core.queue import TaskQueue

async def main():
    logger.info("👷 Worker Starting (Async)...")
    
    # Initialize DB (Pool)
    try:
        await AsyncDatabase.initialize()
    except Exception as e:
        logger.critical(f"Worker failed to connect to DB: {e}", exc_info=True)
        return

    # Run Loops
    try:
        # Run both Cron and Queue in parallel
        await asyncio.gather(
            IrCron.runner_loop(),
            TaskQueue.worker()
        )
    except KeyboardInterrupt:
        logger.info("Worker Stopping...")
    except Exception as e:
        logger.critical(f"Worker Crashed: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
