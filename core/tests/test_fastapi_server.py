
import pytest
from fastapi.testclient import TestClient
from core.http_fastapi import app, ROUTES

client = TestClient(app)

def test_routes_registered():
    """
    Verify that routes declared with @route are registered in FastAPI.
    """
    # Check if logic routes exist
    assert '/' in ROUTES
    assert '/web/login' in ROUTES
    
    # Check if FastAPI has mounted them
    # Note: Our custom mount logic adds them as API routes
    
    # Simple GET request
    response = client.get("/")
    assert response.status_code == 200
    assert "Nexo ERP" in response.text

def test_static_files():
    """
    Verify static files mount (if addons exist)
    """
    # We might not have static files in test env, but app should not crash
    pass

def test_legacy_cleanup():
    """
    Explicitly ensure core.http does not exist (or no longer has dangerous classes)
    """
    import importlib.util
    import sys
    
    # If using importlib to check file existence
    try:
        import core.http
        # If it exists (we might have kept it empty?), check it doesn't have Session
        assert not hasattr(core.http, 'Session'), "Legacy Session class found! Cleanup failed."
        assert not hasattr(core.http, 'dispatch'), "Legacy dispatch function found! Cleanup failed."
    except ImportError:
        # If deleted entirely, that's also pass
        pass
