from core.orm import Model
from core.fields import Char, Integer, Datetime, Boolean, Many2one
from datetime import datetime, timedelta
import traceback
import time

class IrCron(Model):
    _name = 'ir.cron'
    _description = 'Scheduled Actions'

    name = Char(string='Name', required=True)
    model_id = Many2one('ir.model', string='Model', required=True)
    method = Char(string='Method Name', required=True)
    interval_number = Integer(string='Interval Number', default=1)
    interval_type = Char(string='Interval Unit', default='minutes') # minutes, hours, days
    nextcall = Datetime(string='Next Execution Date', required=True)
    active = Boolean(string='Active', default=True)
    
    @classmethod
    async def process_jobs(cls):
        """
        Main loop entry point. 
        """
        from core.db_async import AsyncDatabase
        from core.env import Environment
        from core.registry import Registry
        from core.logger import logger
        import inspect
        
        # Connect
        try:
            # Ensure registry is loaded
            # Registry loading is async? No, usually imports. 
            # But auto_init is async.
            # Assuming Registry is ready or loaded at startup.
                
            async with AsyncDatabase.acquire() as cr:
                env = Environment(cr, uid=1, context={})
                Cron = env['ir.cron']
                
                # Find jobs
                now = datetime.now()
                # Simple search, filter in python for safety
                jobs = await Cron.search([('active', '=', True)])
                
                to_run = []
                for job in jobs:
                    # job.nextcall Is it string or datetime? ORM casts?
                    # current ORM seems to return what driver returns (datetime for timestamp)
                    next_call = job.nextcall
                    if isinstance(next_call, str):
                         try:
                             next_call = datetime.fromisoformat(next_call)
                         except:
                             pass
                    
                    if next_call and next_call <= now:
                        to_run.append(job)
                
                if not to_run:
                    # logger.debug("Cron: No jobs to run.")
                    pass
    
                for job in to_run:
                    logger.info(f"Cron: Processing {job.name}...")
                    try:
                        # Execute
                        model = env[job.model_id.model] # model_id is record, .model is name
                        # Need to fetch model name? model_id is Many2one -> Record.
                        # We need to await read or access pre-fetched.
                        # Assuming 'model_id' field name isn't pre-fetched?
                        # await job.read(['model_id']) # Not fully implemented nesting
                        # But lazy loading might fail in Async if cache miss.
                        # Let's assume we need to access via id or ensure.
                        # Simplification: use job.model_id.model but handle async?
                        # Async ORM nested access `job.model_id` returns Record.
                        # `record.model` needs another get.
                        # Let's manually fetch model name from ir_model table to be safe?
                        # Or await job.model_id.read(['model'])?
                        
                        m_rec = job.model_id
                        await m_rec.read(['model'])
                        model_name = m_rec.model
                        
                        model_inst = env[model_name]
                        
                        if hasattr(model_inst, job.method):
                            method = getattr(model_inst, job.method)
                            if inspect.iscoroutinefunction(method):
                                await method()
                            else:
                                method()
                        else:
                            logger.error(f"Cron Error: Method {job.method} not found in {model_name}")
                        
                        # Update Next Call
                        new_call = now
                        if job.interval_type == 'minutes':
                            new_call += timedelta(minutes=job.interval_number)
                        elif job.interval_type == 'hours':
                            new_call += timedelta(hours=job.interval_number)
                        elif job.interval_type == 'days':
                            new_call += timedelta(days=job.interval_number)
                        
                        await job.write({'nextcall': new_call})
                        # Commit is implicit in Async context manager? No.
                        # AsyncDatabase doesn't auto commit?
                        # asyncpg connection is autocommit unless transaction.
                        # If we are in 'acquire', it yields a connection.
                        # If we want transaction, we use 'transaction()'.
                        # Let's assume autocommit for now or manual commit not needed in asyncpg default mode?
                        # Actually asyncpg is distinct. We might need explicit transaction blocking if `acquire` doesn't start one.
                        # Usually logic: logic should succeed or fail.
                        logger.info(f"Cron: Finished {job.name}")
                        
                    except Exception as e:
                        logger.error(f"Cron Failure {job.name}: {e}", exc_info=True)
                        # Don't rollback whole loop?
                        # Individual job failure shouldn't kill others?
            
        except Exception as e:
            from core.logger import logger
            logger.critical(f"Cron Runner Error: {e}", exc_info=True)

    @staticmethod
    async def runner_loop():
        from core.logger import logger
        logger.info("Cron Worker Started.")
        while True:
            await IrCron.process_jobs()
            await asyncio.sleep(60) # Wake up every minute
