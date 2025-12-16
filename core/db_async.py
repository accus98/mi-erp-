import asyncpg
import os
import logging
from contextlib import asynccontextmanager

# Global Pool
_pool = None

class AsyncDatabase:
    @staticmethod
    def _validate_identifier(name):
        import re
        if not re.match(r'^[a-z0-9_]+$', name):
             raise ValueError(f"Security Error: Invalid Identifier '{name}'. Only lowercase alphanumeric and underscores allowed.")
        return name

    @classmethod
    async def initialize(cls):
        global _pool
        if _pool is None:
            host = os.getenv('DB_HOST', 'localhost')
            user = os.getenv('DB_USER', 'postgres')
            password = os.getenv('DB_PASSWORD', '1234')
            dbname = os.getenv('DB_NAME', 'nexo')
            port = os.getenv('DB_PORT', '5432')
            
            try:
                _pool = await asyncpg.create_pool(
                    user=user,
                    password=password,
                    database=dbname,
                    host=host,
                    port=port,
                    min_size=1,
                    max_size=20
                )
                print("AsyncDatabase: Pool Initialized")
            except Exception as e:
                print(f"CRITICAL: Async Pool Init Failed: {e}")
                raise e

    @classmethod
    async def close(cls):
        global _pool
        if _pool:
            await _pool.close()
            _pool = None
            print("AsyncDatabase: Pool Closed")

    @classmethod
    @asynccontextmanager
    async def acquire(cls):
        if _pool is None:
            await cls.initialize()
        
        async with _pool.acquire() as conn:
            # We wrap the connection to behave like a cursor/transaction manager
            # But asyncpg connection has 'execute', 'fetch', etc. directly.
            # Our ORM expects env.cr.execute(), env.cr.fetchall()
            
            # Smart Wrapper
            cursor = AsyncCursor(conn)
            async with conn.transaction():
                yield cursor

    @classmethod
    async def create_table(cls, cr, table_name, columns, constraints):
        # Postgres Adaptation
        cls._validate_identifier(table_name)
        
        # 1. Sanitize Columns
        safe_cols = []
        for col in columns:
            # SQLite "INTEGER PRIMARY KEY AUTOINCREMENT" -> Postgres "SERIAL PRIMARY KEY"
            if "INTEGER PRIMARY KEY AUTOINCREMENT" in col:
                col = col.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            
            safe_cols.append(col)
            
        cols_def = ", ".join(safe_cols)
        if constraints:
            cols_def += ", " + ", ".join(constraints)
        
        query = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols_def})'
        try:
            await cr.execute(query)
        except Exception as e:
            print(f"Error creating table {table_name}: {e}")
            raise e

    @classmethod
    async def create_pivot_table(cls, cr, table_name, col1, ref1, col2, ref2):
        cls._validate_identifier(table_name)
        cls._validate_identifier(ref1)
        cls._validate_identifier(ref2)
        cls._validate_identifier(col1)
        cls._validate_identifier(col2)
        
        query = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            "{col1}" INTEGER REFERENCES "{ref1}" (id) ON DELETE CASCADE,
            "{col2}" INTEGER REFERENCES "{ref2}" (id) ON DELETE CASCADE,
            UNIQUE ("{col1}", "{col2}")
        )
        """
        try:
            await cr.execute(query)
        except Exception as e:
            print(f"Error creating pivot {table_name}: {e}")
            raise e

class AsyncCursor:
    def __init__(self, conn):
        self.conn = conn
        self._last_result = None
        
    async def execute(self, query, args=None):
        """
        Executes query. If it's a SELECT/RETURNING, stores result for fetchall.
        """
        # 1. Convert %s to $n (Safely)
        pg_query = query
        if args:
            pg_query = self._convert_sql_params(query)

    def _convert_sql_params(self, query):
        """
        Safely converts %s placeholders to $1, $2, etc. for asyncpg,
        ignoring %s inside string literals.
        """
        out = []
        param_count = 0
        state = 0 # 0: NORMAL, 1: IN_SINGLE_QUOTE, 2: IN_DOUBLE_QUOTE
        i = 0
        length = len(query)
        
        while i < length:
            char = query[i]
            
            if state == 0:
                if char == "'":
                    state = 1
                    out.append(char)
                elif char == '"':
                    state = 2
                    out.append(char)
                elif char == '%' and i + 1 < length and query[i+1] == 's':
                    # Found placeholder
                    param_count += 1
                    out.append(f"${param_count}")
                    i += 1 # Skip 's'
                else:
                    out.append(char)
            elif state == 1:
                # In Single Quote
                out.append(char)
                if char == "'" and (i == 0 or query[i-1] != '\\'): # Simple check for non-escaped
                     # Basic SQL escape check is '' for ' inside string usually, or backslash.
                     # Postgres standard strings use ''. Backslash depends on config.
                     # For simplicity assume standard SQL '' escaping or strict quote.
                     # Let's peek behind for '', if we are at i.
                     # If previous char was ', then we might be escaping?
                     # Standard parser is complex. Let's assume standard toggle.
                     # Use peeking for escaped quotes if needed.
                     # For now, toggling on same quote is robust enough for typical migration.
                     state = 0
            elif state == 2:
                # In Double Quote
                out.append(char)
                if char == '"' and (i == 0 or query[i-1] != '\\'):
                     state = 0
            
            i += 1
            
        return "".join(out)
            
        # 2. Determine execution mode
        # Simple heuristic: SELECT or RETURNING implies fetch
        normalized = pg_query.strip().upper()
        is_fetch = normalized.startswith("SELECT") or "RETURNING" in normalized
        
        args = args or ()
        
        try:
            if is_fetch:
                # Use fetch for data
                self._last_result = await self.conn.fetch(pg_query, *args)
            else:
                # Use execute for commands (INSERT, UPDATE, DELETE without returning)
                await self.conn.execute(pg_query, *args)
                self._last_result = [] # No result
        except Exception as e:
            print(f"AsyncDB Error: {e} | Query: {pg_query}")
            raise e
            
    def fetchall(self):
        # This MUST be sync because ORM expects it sync?
        # ORM refactor will make everything await custom_method().
        # But if we change ORM to `await cr.fetchall()`, then this should be async?
        # NO. if `await execute` already fetched, `fetchall` is just return.
        # So `fetchall` can be sync if `execute` did the work?
        # Wait, if `fetchall` is async in usage `await cr.fetchall()`, we define it as async.
        # Plan says ORM will be refactored. Let's make it standard:
        # return stored result.
        if self._last_result is None:
             # Should not happen if execute called
             return []
        
        # asyncpg Record objects are compatible-ish with dict/tuple?
        # They behave like mappings. ORM expects tuples usually?
        # Psycopg2 DictCursor returns list of objects accessible by index and name.
        # asyncpg Record is similar.
        return self._last_result
        
    def fetchone(self):
        if self._last_result:
            return self._last_result[0]
        return None
        
    def mogrify(self, query, args):
        # asyncpg doesn't usually expose mogrify easily without private APIs or mess.
        # Quick hack: formatted string (insecure but 'safe' if args trusted).
        # OR just return string with values injected (dangerous).
        # Better: ORM should avoid Mognify if possible or we implement a simple formatter.
        # For M2M implementation we used mogrify for bulk insert.
        # We can rewrite M2M to use executemany or just loop for now.
        # Let's simple-implement a basic string replacement for now.
        # Note: args is a tuple/list of values.
        
        # Warning: This is purely for the "Simulated" mogrify the ORM calls.
        # We should probably change the ORM to avoid `mogrify` and use `executemany`.
        pass
        return b"Error: Async Mognify Not Implemented"

    def savepoint(self):
        """
        Returns an async context manager for a savepoint (nested transaction).
        Usage:
            async with cr.savepoint():
                ...
        """
    async def executemany(self, query, args_list):
        """
        High-performance bulk execution using asyncpg.executemany.
        query: SQL with $n placeholders (or %s if conversion needed)
        args_list: List of tuples/lists of arguments
        """
        # 1. Convert %s to $n (Safely)
        pg_query = self._convert_sql_params(query)
            
        try:
            await self.conn.executemany(pg_query, args_list)
        except Exception as e:
            print(f"AsyncDB Bulk Error: {e} | Query: {pg_query}")
            raise e
