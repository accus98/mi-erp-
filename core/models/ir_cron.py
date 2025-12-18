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
        
        # 1. Fetch Jobs (Short Transaction)
        jobs_data = [] # (id, name, nextcall, interval...)
        try:
            async with AsyncDatabase.acquire() as cr:
                env = Environment(cr, uid=1, context={})
                Cron = env['ir.cron']
                
                # Check for jobs due
                # We fetch matching IDs and basic data to avoid holding the cursor
                # active while processing jobs (which might take time).
                # Actually, iterate search result.
                
                now = datetime.now()
                # Search Active
                # We need to use SQL or ORM. ORM is fine.
                candidates = await Cron.search([('active', '=', True)])
                
                for candidate in candidates:
                    # Parse nextcall
                    nxt = candidate.nextcall
                    if isinstance(nxt, str):
                        try:
                            nxt = datetime.fromisoformat(nxt)
                        except:
                            continue
                    
                    if nxt and nxt <= now:
                         jobs_data.append(candidate.id)
                         
        except Exception as e:
            logger.error(f"Cron Fetch Error: {e}")
            return

        if not jobs_data:
             return

        # 2. Process Each Job (Isolated Transaction)
        for job_id in jobs_data:
             await cls._run_job_isolated(job_id)

    @classmethod
    async def _run_job_isolated(cls, job_id):
        from core.db_async import AsyncDatabase
        from core.env import Environment
        from core.logger import logger
        import inspect
        from datetime import datetime, timedelta
        
        try:
            async with AsyncDatabase.acquire() as cr:
                env = Environment(cr, uid=1, context={})
                job = await env['ir.cron'].browse([job_id]).read()
                if not job: return # Deleted?
                job = env['ir.cron'].browse([job_id]) # Browse object
                
                logger.info(f"Cron: Processing {job.name}...")
                
                # Lock job? (Optional for now, single worker assumed)
                
                # Resolve Model/Method
                # Need to read relation field 'model' from 'model_id'
                # Pre-read model_id to ensure we have it
                m_rec = job.model_id
                await m_rec.read(['model'])
                model_name = m_rec.model
                
                if model_name not in env:
                    logger.error(f"Cron Error: Model {model_name} not found registry.")
                    return

                model_inst = env[model_name]
                
                if hasattr(model_inst, job.method):
                    method = getattr(model_inst, job.method)
                    
                    # Execute
                    if inspect.iscoroutinefunction(method):
                        await method()
                    else:
                        method()
                        
                    # Update Next Call
                    now = datetime.now()
                    new_call = now
                    if job.interval_type == 'minutes':
                        new_call += timedelta(minutes=job.interval_number)
                    elif job.interval_type == 'hours':
                        new_call += timedelta(hours=job.interval_number)
                    elif job.interval_type == 'days':
                        new_call += timedelta(days=job.interval_number)
                    
                    await job.write({'nextcall': new_call})
                    logger.info(f"Cron: Finished {job.name}")
                    
                else:
                    logger.error(f"Cron Error: Method {job.method} not found in {model_name}")

        except Exception as e:
            logger.error(f"Cron Failure Job {job_id}: {e}", exc_info=True)
            # Transaction (acquire block) rolls back automatically on exception.
            # Other jobs are unaffected.

    @staticmethod
    async def runner_loop():
        from core.logger import logger
        logger.info("Cron Worker Started.")
        while True:
            await IrCron.process_jobs()
            await asyncio.sleep(60) # Wake up every minute
