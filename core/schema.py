
import asyncio
from core.registry import Registry
from core.db_async import AsyncDatabase
from core.fields import Many2many, Many2one

class SchemaManager:
    def __init__(self, cr):
        self.cr = cr
        
    async def migrate_all(self):
        """
        Check all registered models and sync schema.
        """
        print("SchemaManager: Starting Migration...")
        for name, model_cls in Registry.models.items():
            if name == 'base': continue # Abstract/Dummy
            if model_cls._auto:
                 await self.sync_model(model_cls)
        print("SchemaManager: Migration Complete.")

    async def sync_model(self, model_cls):
        table = model_cls._table
        
        # 1. Get Existing Columns
        query = f"""
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = '{table}'
        """
        await self.cr.execute(query)
        rows = self.cr.fetchall()
        existing_cols = {r['column_name']: r for r in rows}
        
        if not existing_cols:
             # Table likely doesn't exist. Model._auto_init should handle it, or we call it?
             # Usually _auto_init is called at startup. 
             # SchemaManager is run post-init or as a tool.
             # If table missing, we assume _auto_init runs elsewhere or we trigger it.
             # Let's assume table exists or we skip.
             # Actually, best to call _auto_init if missing?
             # Model._auto_init is classmethod.
             # For now, focus on ALTER.
             return

        # 2. Check Fields
        for name, field in model_cls._fields.items():
            if not field._sql_type: continue # Non-stored (M2M/One2many/Compute)
            
            if name not in existing_cols:
                # MISSING COLUMN -> ADD
                print(f"Schema: Adding column {table}.{name} ({field._sql_type})")
                
                # Determine Default? Field.default is often python callable.
                # Adding NOT NULL requires default.
                # For V1, we add as NULLable usually.
                
                sql_type = field._sql_type
                # Handle specific PG types if needed? _sql_type is usually generic ('VARCHAR', 'INTEGER')
                # Many2one -> INTEGER.
                
                alter_sql = f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}'
                
                # Add Foreign Key constraint immediately for M2o?
                # Model._auto_init does it inline. We must add CONSTRAINT if missing.
                # Constraint naming is tricky. Postgres auto-names or we name it.
                # V1: Just add column. Relations might need manual FK later or we add it now.
                
                await self.cr.execute(alter_sql)
                
                if isinstance(field, Many2one):
                     ref_table = Registry.get(field.comodel_name)._table
                     # constraint name?
                     # ALTER TABLE table ADD CONSTRAINT fk_name FOREIGN KEY (col) REFERENCES ref (id) ...
                     # We can skip explicit name and let PG handle or use convention.
                     await self.cr.execute(f'ALTER TABLE "{table}" ADD FOREIGN KEY ("{name}") REFERENCES "{ref_table}" (id) ON DELETE {field.ondelete.upper()}')

            else:
                # Column exists. Check Type?
                # db_type = existing_cols[name]['udt_name'] # e.g. varchar, int4
                # field._sql_type e.g. 'VARCHAR', 'INTEGER’.
                # Mapping is hard (int4 vs INTEGER).
                # Skip type check for V1 unless critical mismatch.
                pass
