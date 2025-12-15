
import sqlite3
import json

def debug_db():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Schema of ir_ui_menu ---")
    cursor.execute("PRAGMA table_info(ir_ui_menu)")
    cols = cursor.fetchall()
    for c in cols:
        print(c)
        
    print("\n--- Inspecting First Menu ---")
    # Just select *
    cursor.execute("SELECT * FROM ir_ui_menu LIMIT 1")
    print(cursor.fetchone())

    print("\n--- Inspecting Action 1 ---")
    cursor.execute("SELECT * FROM ir_actions_act_window WHERE id=1")
    print(cursor.fetchone())
    
    conn.close()

if __name__ == "__main__":
    debug_db()
