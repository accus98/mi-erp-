import sys
import os
import time

# Add root directory to python path
sys.path.append(os.getcwd())

from core.logger import logger
from core.db import Database
from core.models.ir_cron import IrCron

def main():
    logger.info("👷 Cron Worker Starting...")
    
    # Initialize DB (Pool)
    try:
        Database.connect()
    except Exception as e:
        logger.critical(f"Worker failed to connect to DB: {e}", exc_info=True)
        return

    # Run Loop
    try:
        IrCron.runner_loop()
    except KeyboardInterrupt:
        logger.info("Worker Stopping...")
    except Exception as e:
        logger.critical(f"Worker Crashed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
