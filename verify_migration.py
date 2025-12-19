
import sys
import os

print("Verifying Migration...")

try:
    # 1. Check if core.http is gone
    try:
        import core.http
        print("FAIL: core.http still exists!")
        sys.exit(1)
    except ImportError:
        print("PASS: core.http is correctly removed.")

    # 2. Check Routing
    from core.routing import ROUTES, route, Response
    print("PASS: core.routing is importable.")

    # 3. Check Controllers
    # This should import core.routing internally
    from core.controllers import main
    print("PASS: core.controllers.main imported (Route annotations worked).")

    # 4. Check Server
    from core.http_fastapi import app
    print("PASS: core.http_fastapi imported successfully.")
    
    print("SUCCESS: Migration Verified.")

except Exception as e:
    print(f"FAIL: Verification Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
