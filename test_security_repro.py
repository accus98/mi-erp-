import sys
import os
sys.path.append(os.getcwd())

from core.db import Database
from core.registry import Registry
from core.env import Environment
from core.orm import Model
from core.fields import Char

class TestSecurity(Model):
    _name = 'test.security'
    name = Char(string="Name")

def run_test():
    print("--- Security Vulnerability Reproduction ---")
    try:
        conn = Database.connect()
        cr = Database.cursor(conn)
        Registry.register('test.security', TestSecurity)
        Registry.setup_models(cr)
        
        env = Environment(cr, uid=1)
        
        # 1. SQL Injection in ORDER BY
        print("\n[1] Testing ORDER BY Injection...")
        try:
            # Malicious payload: "name; --" (Validation should block this)
            # Or worse: "name; DROP TABLE test_security; --"
            # But standard execute() might not support multiple statements depending on driver.
            # However, "name DESC, (SELECT...)" might work for blind injection.
            
            # Let's try a syntax error payload to confirm raw injection
            payload = "name; SELECT 1"
            print(f"Injecting payload: {payload}")
            
            # This should either fail with Syntax Error (if injected) 
            # OR pass (if correctly sanitized/quoted? No, pure strings shouldn't pass if validated)
            # OR fail with 'Invalid Field' if we fix it.
            
            env['test.security'].search([], order=payload)
            print("FAILURE: Exploit executed (or silently accepted).")
        except Exception as e:
            msg = str(e)
            if 'syntax error' in msg.lower() or 'error de sintaxis' in msg.lower():
                print(f"CONFIRMED VULNERABILITY: Database reported syntax error: {e}")
            elif 'invalid order field' in msg.lower():
                print(f"SUCCESS: System blocked valid injection attempt: {e}")
            else:
                 print(f"Unknown Result: {e}")

        conn.rollback()
        conn.close()
        
    except Exception as e:
        print(f"Test Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()
