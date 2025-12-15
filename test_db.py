import sys
import os
import time

# Add current directory to path
sys.path.append(os.getcwd())

from core.orm import Model, Char, Integer
from core.db import Database
from addons.base.models import ResPartner

def run_test():
    print("--- 1. Connecting to Database ---")
    try:
        # User might not have a local DB "nexo_erp" created.
        # This will fail if not set up, but that's expected for verification.
        conn = Database.connect()
        cr = Database.cursor(conn)
        print("Connected successfully.")
    except Exception as e:
        # Use repr to avoid encoding errors on localized Windows
        print(f"Skipping DB test because connection failed: {repr(e)}")
        print("Please ensure you have a standard Postgres DB running and set env vars if needed.")
        return

    print("\n--- 2. Registering and Initializing Tables ---")
    # ResPartner is already registered by import
    try:
        ResPartner._auto_init(cr)
        conn.commit()
        print("Table res_partner ensured.")
    except Exception as e:
        conn.rollback()
        print(f"Failed to init table: {e}")
        return

    print("\n--- 3. Testing CRUD ---")
    try:
        # CREATE
        pid = ResPartner.create(cr, {'name': 'Tech Corp', 'email': 'info@tech.com'})
        print(f"Created Partner ID: {pid}")
        
        # BROWSE
        partners = ResPartner.browse(cr, [pid])
        p = partners[0]
        print(f"Browsed: {p.name}, {p.email}, Created: {p.create_date}")
        
        # WRITE
        ResPartner.write(cr, [pid], {'name': 'Tech Corp International'})
        
        # SEARCH
        ids = ResPartner.search(cr, [('name', 'ilike', 'Tech%')])
        print(f"Search found IDs: {ids}")
        
        if pid in ids:
            print("SUCCESS: CRUD Flow verified.")
        else:
            print("FAILURE: ID not found after update.")

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"CRUD Error: {e}")
    finally:
        Database.release(conn)

if __name__ == "__main__":
    run_test()
