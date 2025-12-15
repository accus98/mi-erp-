
import sqlite3
import sys

def cleanup_orphans():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Cleaning Orphan Menus (Parent Deleted) ---")
    cursor.execute("""
        DELETE FROM ir_ui_menu 
        WHERE parent_id IS NOT NULL 
          AND parent_id NOT IN (SELECT id FROM ir_ui_menu)
    """)
    print(f"Deleted {cursor.rowcount} orphan menus.")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    cleanup_orphans()
