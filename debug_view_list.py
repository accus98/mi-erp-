
import sqlite3
import sys

def list_views():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Listing All Views ---")
    cursor.execute("SELECT id, name, model, type, arch FROM ir_ui_view")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Name: {row[1]}, Model: {row[2]}, Type: {row[3]}, Arch Len: {len(row[4]) if row[4] else 0}")
        if row[2] == 'sale.order':
            print("FULL ARCH:", row[4])
    
    conn.close()

if __name__ == "__main__":
    list_views()
