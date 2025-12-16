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
    def process_jobs(cls):
        """
        Main loop entry point. 
        """
        from core.db import Database
        from core.env import Environment
        from core.registry import Registry
        from core.logger import logger
        
        # Connect
        try:
            # Connect via Pool
            conn = Database.connect()
            cr = Database.cursor(conn)
            
            # Ensure registry is loaded (might be reloaded if new worker)
            if not Registry.models:
                Registry.setup_models(cr)
                
            env = Environment(cr, uid=1)
            Cron = env['ir.cron']
            
            # Find jobs
            now = datetime.now()
            # Simple search, filter in python for safety
            jobs = Cron.search([('active', '=', True)])
            
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
                    if hasattr(model, job.method):
                        getattr(model, job.method)()
                    else:
                        logger.error(f"Cron Error: Method {job.method} not found in {model._name}")
                    
                    # Update Next Call
                    new_call = now
                    if job.interval_type == 'minutes':
                        new_call += timedelta(minutes=job.interval_number)
                    elif job.interval_type == 'hours':
                        new_call += timedelta(hours=job.interval_number)
                    elif job.interval_type == 'days':
                        new_call += timedelta(days=job.interval_number)
                    
                    job.write({'nextcall': new_call})
                    conn.commit()
                    logger.info(f"Cron: Finished {job.name}")
                    
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Cron Failure {job.name}: {e}", exc_info=True)
            
            Database.release(conn)
            
        except Exception as e:
            from core.logger import logger
            logger.critical(f"Cron Runner Error: {e}", exc_info=True)

    @staticmethod
    def runner_loop(db_params=None):
        from core.logger import logger
        logger.info("Cron Worker Started.")
        while True:
            IrCron.process_jobs()
            time.sleep(60) # Wake up every minute
