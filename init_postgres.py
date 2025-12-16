
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def init_db():
    print("Connecting to 'postgres' system database...")
    try:
        # Connect to default 'postgres' db to create our db
        con = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            host='localhost',
            password='1234'
        )
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = con.cursor()
        
        # Check if DB exists
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'nexo'")
        exists = cur.fetchone()
        
        if not exists:
            print("Database 'nexo' not found. Creating...")
            cur.execute('CREATE DATABASE nexo')
            print("Database 'nexo' created.")
        else:
            print("Database 'nexo' already exists.")
            
        cur.close()
        con.close()
        
    except Exception as e:
        print(f"Error initializing DB: {e}")
        return False
        
    return True

if __name__ == "__main__":
    if init_db():
        print("Initialization Complete.")
        
        # Verify connection to nexo
        try:
             con = psycopg2.connect(
                dbname='nexo',
                user='postgres',
                host='localhost',
                password='1234'
            )
             print("Successfully connected to 'nexo' database!")
             con.close()
        except Exception as e:
            print(f"Failed to connect to 'nexo' database: {e}")
