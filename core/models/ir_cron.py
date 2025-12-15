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
    def process_jobs(cls, db_params):
        """
        Main loop entry point. 
        db_params: dict for Database.connect()
        """
        from core.db import Database
        from core.env import Environment
        from core.registry import Registry
        
        # Connect
        try:
            # We create a fresh connection per loop or reuse? 
            # Ideally short lived connection.
            conn = Database.connect(**db_params)
            cr = Database.cursor(conn)
            
            # Ensure registry is loaded (might be reloaded if new worker)
            if not Registry.models:
                Registry.setup_models(cr)
                
            env = Environment(cr, uid=1)
            Cron = env['ir.cron']
            
            # Find jobs
            now = datetime.now()
            jobs = Cron.search([
                ('active', '=', True),
                # ('nextcall', '<=', now) # Comparison in string domain might fail if not handled well yet?
                # Domain parser supports <=. Value needs to be string iso? 
                # Let's rely on SQL string injection or python filter if parser weak.
                # Domain parser: "field <= val".
            ])
            
            # Filter manually for safety if domain parser date handling is MVP
            to_run = []
            for job in jobs:
                if job.nextcall and job.nextcall <= now:
                    to_run.append(job)
            
            for job in to_run:
                print(f"Cron: Processing {job.name}...")
                try:
                    # Execute
                    model = env[job.model_id.model] # model_id is record, .model is name
                    if hasattr(model, job.method):
                        getattr(model, job.method)()
                    else:
                        print(f"Cron Error: Method {job.method} not found in {model._name}")
                    
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
                    print(f"Cron: Finished {job.name}")
                    
                except Exception as e:
                    conn.rollback()
                    print(f"Cron Failure {job.name}: {e}")
                    traceback.print_exc()
            
            Database.release(conn)
            
        except Exception as e:
            print(f"Cron Runner Error: {e}")
            traceback.print_exc()

    @staticmethod
    def runner_loop(db_params):
        while True:
            IrCron.process_jobs(db_params)
            time.sleep(60) # Wake up every minute
