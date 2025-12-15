
import sqlite3
import sys

def debug_schema():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Schema of ir_actions_act_window ---")
    cursor.execute("PRAGMA table_info(ir_actions_act_window)")
    for c in cursor.fetchall():
        print(c)
    
    conn.close()
    sys.stdout.flush()

if __name__ == "__main__":
    debug_schema()
