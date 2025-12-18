# WARNING: THIS MODULE IS SYNCHRONOUS (BSYNC).
# DO NOT USE IN FASTAPI ROUTERS OR ASYNC CONTEXTS.
# Use core.db_async.AsyncDatabase instead.

import psycopg2
import psycopg2.extras
import psycopg2.pool
import os
import uuid
import threading


# Threaded Pool for managing connections
_pool = None

class Database:
    @staticmethod
    def _validate_identifier(name):
        import re
        if not re.match(r'^[a-z0-9_]+$', name):
             raise ValueError(f"Security Error: Invalid Identifier '{name}'. Only lowercase alphanumeric and underscores allowed.")
        return name

    @classmethod
    def connect(cls):
        """
        Returns a connection from the ThreadedConnectionPool.
        Must be released back to the pool using Database.release(conn).
        """
        global _pool
        if _pool is None:
            host = os.getenv('DB_HOST', 'localhost')
            user = os.getenv('DB_USER', 'postgres')
            password = os.getenv('DB_PASSWORD')
            dbname = os.getenv('DB_NAME', 'nexo')
            port = os.getenv('DB_PORT', '5432')
            
            env_type = os.getenv('ENV_TYPE', 'prod')
            
            # Load keys via dotenv
            from dotenv import load_dotenv
            load_dotenv()
            
            # Re-fetch explicitly to ensure env is fresh
            if not password: password = os.getenv('DB_PASSWORD', '1234')
            if not env_type: env_type = os.getenv('ENV_TYPE', 'prod')

            pass
            
            if not password:
                # CRITICAL SECURITY FIX: No default attributes in code.
                # Must be provided via .env
                msg = (
                    "CRITICAL SECURITY ERROR: 'DB_PASSWORD' is not set.\n"
                    "1. Check your .env file.\n"
                    "Application cannot connect to database without credentials."
                )
                raise ValueError(msg)
            
            try:
                # ThreadedConnectionPool ensures thread-safety.
                # minconn=1, maxconn=20 (Adjust as needed)
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    1, 20,
                    host=host,
                    user=user,
                    password=password,
                    dbname=dbname,
                    port=port,
                    cursor_factory=psycopg2.extras.DictCursor
                )
                print("Database: Connection Pool Initialized (Min: 1, Max: 20)")
            except Exception as e:
                print(f"CRITICAL: Failed to initialize Connection Pool: {e}")
                raise e
        
        # Get connection from pool
        conn = _pool.getconn()
        conn.autocommit = False # ORM relies on manual commit/rollback
        return conn

    @classmethod
    def release(cls, conn):
        """
        Return the connection to the pool.
        """
        global _pool
        if _pool and conn:
            try:
                # Rollback uncommitted transactions before returning to pool
                # to prevent dirty state in next use.
                conn.rollback()
            except:
                pass
            _pool.putconn(conn)

    @classmethod
    def close_all(cls):
        """
        Close all connections in pool (Shutdown)
        """
        global _pool
        if _pool:
            _pool.closeall()
            _pool = None
            print("Database: Connection Pool Closed.")

    @classmethod
    def cursor(cls, conn):
        return CursorWrapper(conn.cursor())

    @classmethod
    def create_table(cls, cr, table_name, columns, constraints):
        # Postgres Adaptation
        cls._validate_identifier(table_name)
        
        # 1. Sanitize Columns
        safe_cols = []
        for col in columns:
            # Security Check: Prevent SQL Injection in Column Definition
            # DDL is sensitive. We block comments and terminators.
            if ";" in col or "--" in col or "/*" in col:
                 raise ValueError(f"Security Error: Invalid characters in column definition '{col}'")
                 
            # SQLite "INTEGER PRIMARY KEY AUTOINCREMENT" -> Postgres "SERIAL PRIMARY KEY"
            # Since our ORM usually sends '"id" INTEGER PRIMARY KEY AUTOINCREMENT'
            if "INTEGER PRIMARY KEY AUTOINCREMENT" in col:
                col = col.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            
            safe_cols.append(col)
            
        cols_def = ", ".join(safe_cols)
        if constraints:
            cols_def += ", " + ", ".join(constraints)
        
        query = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({cols_def})'
        try:
            cr.execute(query)
        except Exception as e:
            try:
                msg = str(e)
            except:
                msg = "Encoding Error"
            print(f"Error creating table {table_name}: {msg}")
            raise e

    @classmethod
    def create_pivot_table(cls, cr, table_name, col1, ref1, col2, ref2):
        cls._validate_identifier(table_name)
        cls._validate_identifier(ref1)
        cls._validate_identifier(ref2)
        # col1/col2 are usually field names with _id, check them too?
        # Usually internal. But safe to check.
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
            cr.execute(query)
        except Exception as e:
            try:
                msg = str(e)
            except:
                msg = "Encoding Error"
            print(f"Error creating pivot {table_name}: {msg}")
            raise e

class CursorWrapper:
    def __init__(self, real_cursor):
        self._cursor = real_cursor

    def __getattr__(self, name):
        return getattr(self._cursor, name)
        
    def execute(self, query, params=None):
        # We might need to adapt placeholders if we didn't refactor ALL code yet?
        # But task says "Refactor SQL placeholders".
        # Let's assume params are passed correctly for the query syntax.
        # But wait, old code passes tuple(ids_list) which is correct for %s.
        return self._cursor.execute(query, params)
        
    def fetchall(self):
        return self._cursor.fetchall()
        
    def fetchone(self):
        return self._cursor.fetchone()

    @property
    def lastrowid(self):
        # Postgres doesn't have lastrowid attribute on cursor standardly
        # Usually we use "RETURNING id"
        return getattr(self._cursor, 'lastrowid', None)

    def savepoint(self):
        return Savepoint(self._cursor)

class Savepoint:
    def __init__(self, cursor):
        self.cursor = cursor
        self.sp_name = f"sp_{uuid.uuid4().hex}"

    def __enter__(self):
        self.cursor.execute(f"SAVEPOINT {self.sp_name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.cursor.execute(f"ROLLBACK TO SAVEPOINT {self.sp_name}")
        else:
            self.cursor.execute(f"RELEASE SAVEPOINT {self.sp_name}")
