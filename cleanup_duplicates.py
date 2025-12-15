
import sqlite3
import sys

def cleanup():
    conn = sqlite3.connect('nexo.db')
    cursor = conn.cursor()
    
    print("--- Cleaning Duplicate Actions ---")
    # Identify duplicates by name and res_model
    cursor.execute("""
        SELECT name, res_model, COUNT(*), MAX(id) 
        FROM ir_actions_act_window 
        GROUP BY name, res_model 
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    
    for name, model, count, max_id in duplicates:
        print(f"Fixing Action '{name}' ({model}): Keeping ID {max_id}, deleting {count-1} others.")
        cursor.execute("""
            DELETE FROM ir_actions_act_window 
            WHERE name=? AND res_model=? AND id != ?
        """, (name, model, max_id))
        
    print("\n--- Cleaning Duplicate Menus ---")
    # Identify duplicates by name and parent_id
    cursor.execute("""
        SELECT name, parent_id, COUNT(*), MAX(id) 
        FROM ir_ui_menu 
        GROUP BY name, parent_id 
        HAVING COUNT(*) > 1
    """)
    dup_menus = cursor.fetchall()
    
    for name, parent, count, max_id in dup_menus:
        parent_str = f"Parent {parent}" if parent else "Root"
        print(f"Fixing Menu '{name}' ({parent_str}): Keeping ID {max_id}, deleting {count-1} others.")
        # Handle NULL parent_id for SQL equality
        if parent is None:
            cursor.execute("""
                DELETE FROM ir_ui_menu 
                WHERE name=? AND parent_id IS NULL AND id != ?
            """, (name, max_id))
        else:
            cursor.execute("""
                DELETE FROM ir_ui_menu 
                WHERE name=? AND parent_id=? AND id != ?
            """, (name, parent, max_id))

    conn.commit()
    conn.close()
    print("\nCleanup Complete.")

if __name__ == "__main__":
    cleanup()
