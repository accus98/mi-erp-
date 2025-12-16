import os
from core.db import Database
from core.auth import get_password_hash

def reset_admin():
    print("--- Reseteando contraseña de Admin ---")
    
    # 1. Generar hash válido
    new_pass = "admin"
    hashed = get_password_hash(new_pass)
    print(f"Nuevo Hash generado: {hashed}")

    # 2. Conectar a BD
    conn = Database.connect()
    cr = conn.cursor()

    try:
        # 3. Actualizar directamente
        # Asumiendo que la tabla es res_users
        query = "UPDATE res_users SET password = %s WHERE login = 'admin'"
        cr.execute(query, (hashed,))
        
        if cr.rowcount == 0:
            print("ERROR: No se encontró el usuario 'admin'.")
        else:
            conn.commit()
            print("¡ÉXITO! La contraseña de 'admin' ha sido restaurada a 'admin' (formato hash).")
            
    except Exception as e:
        conn.rollback()
        print(f"Error fatal: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_admin()
