
import sqlite3
import json
import sys

def debug_db():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Schema of ir_ui_menu ---")
    cursor.execute("PRAGMA table_info(ir_ui_menu)")
    cols = cursor.fetchall()
    for c in cols:
        print(c)
        
    print("\n--- Inspecting Menu 22 (Sales -> Orders) ---")
    cursor.execute("SELECT * FROM ir_ui_menu WHERE id=22")
    row = cursor.fetchone()
    if row:
        print(row)
    else:
        print("Menu 22 not found!")

    print("\n--- Inspecting Action 1 ---")
    cursor.execute("SELECT * FROM ir_actions_act_window WHERE id=1")
    row = cursor.fetchone()
    if row:
        print(row)
    else:
        print("Action 1 not found!")

    print("\n--- Inspecting Views ---")
    cursor.execute("SELECT count(*) FROM ir_ui_view")
    print(f"Total Views: {cursor.fetchone()[0]}")
    
    conn.close()
    sys.stdout.flush()

if __name__ == "__main__":
    debug_db()
