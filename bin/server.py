import sys
import os
import uvicorn

# Ensure project root is in path
sys.path.append(os.getcwd())

if __name__ == "__main__":
    print("Starting Nexo Enterprise Server...")
    # Run Uvicorn logic
    # We reference the module string "core.http_fastapi:app"
    uvicorn.run("core.http_fastapi:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
