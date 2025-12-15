
import sqlite3
import json

def debug_db():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Inspecting Actions ---")
    cursor.execute("SELECT id, name, res_model FROM ir_actions_act_window")
    actions = cursor.fetchall()
    for a in actions:
        print(f"Action ID: {a[0]}, Name: {a[1]}, Model: {a[2]}")

    print("\n--- Inspecting Menus ---")
    cursor.execute("SELECT id, name, action FROM ir_ui_menu")
    menus = cursor.fetchall()
    for m in menus:
        print(f"Menu ID: {m[0]}, Name: {m[1]}, Action: {m[2]}")
        
    conn.close()

if __name__ == "__main__":
    debug_db()
