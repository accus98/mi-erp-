
import unittest
import sys
import os

# Ensure project root is in path if running from subdir
# (This is a fallback, preferably run with python -m core.tests...)
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

from core.db import Database
from core.env import Environment
from core.registry import Registry

class TransactionCase(unittest.TestCase):
    """
    TestCase that executes each test in a rollback transaction.
    """
    
    def setUp(self):
        super().setUp()
        self.conn = Database.connect()
        self.cursor = Database.cursor(self.conn)
        
        # In SQLite/Python, transactions are automatic, but we want to ensure
        # we can rollback to a clean state.
        # Ideally, we rely on the fact that we NEVER commit in tests.
        # But to be safe, we could use savepoints or just simple rollback.
        
        self.uid = 1
        self.env = Environment(self.cursor, self.uid)
        
        # Ensure we are not in a polluted state?
        # self.cursor.execute("BEGIN") # Python DBAPI usually does this automatically on first write.

    def tearDown(self):
        super().tearDown()
        # Rollback all changes made during the test
        self.conn.rollback()
        # Note: We do not close the singleton connection
