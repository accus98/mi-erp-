
import sqlite3
import sys

def debug_view_arch():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Inspecting View Architecture ---")
    cursor.execute("SELECT id, name, arch FROM ir_ui_view WHERE model='sale.order' AND type='tree'")
    row = cursor.fetchone()
    if row:
        print(f"ID: {row[0]}")
        print(f"Name: {row[1]}")
        print(f"Arch: {row[2]}")
    else:
        print("View not found!")
    
    conn.close()

if __name__ == "__main__":
    debug_view_arch()
