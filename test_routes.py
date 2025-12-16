import sys
import os
# Ensure project root in path
sys.path.append(os.getcwd())

from core.http import ROUTES

def run_test():
    print("--- Verifying Routes ---")
    print(f"Initial ROUTES count: {len(ROUTES)}")
    
    # Import http_fastapi which triggers load_modules
    import core.http_fastapi
    
    print(f"Post-load ROUTES count: {len(ROUTES)}")
    print("Registered Routes:")
    for path in ROUTES:
        print(f" - {path}")
        
    if len(ROUTES) > 0 and '/web/login' in ROUTES:
        print("SUCCESS: Routes loaded.")
    else:
        print("FAILURE: Routes missing.")

if __name__ == "__main__":
    run_test()
