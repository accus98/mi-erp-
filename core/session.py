import uuid
import secrets
import os
from fastapi import Request
from core.cache import Cache

# Async Session Logic
# Async Session Logic
class Session:
    def __init__(self, sid):
        self.sid = sid
        self.uid = None
        self.login = None
        self.context = {}
        self._dirty = False 
        
    @classmethod
    async def new(cls):
        # High Entropy Session ID
        sid = secrets.token_urlsafe(32)
        sess = cls(sid)
        sess.csrf_token = secrets.token_urlsafe(32) # Secure CSRF Token
        await sess.save()
        return sess

    @classmethod
    async def load(cls, sid):
        # print(f"DEBUG_SESSION: Loading {sid}")
        data = await Cache.get(f"session:{sid}")
        # print(f"DEBUG_SESSION: Data for {sid}: {data}")
        if data:
            sess = cls(sid)
            sess.uid = data.get('uid')
            sess.login = data.get('login')
            sess.context = data.get('context', {})
            # Auto-heal if missing
            sess.csrf_token = data.get('csrf_token') or secrets.token_urlsafe(32) 
            return sess
        return None

    async def rotate(self):
        """
        Regenerate Session ID to prevent Fixation Attacks.
        """
        old_sid = self.sid
        # Create new ID
        self.sid = secrets.token_urlsafe(32)
        self.csrf_token = secrets.token_urlsafe(32) # Rotate CSRF
        # Save new
        await self.save()
        # Delete old
        await Cache.delete(f"session:{old_sid}")
        # print(f"DEBUG_SESSION: Rotated {old_sid} -> {self.sid}")

    async def save(self):
        data = {
            'uid': self.uid,
            'login': self.login,
            'context': self.context,
            'csrf_token': getattr(self, 'csrf_token', None)
        }
        # TTL 1 day
        await Cache.set(f"session:{self.sid}", data, ttl=86400)


# Dependency for Session
async def get_session(request: Request):
    sid = request.cookies.get('session_id')
    # print(f"DEBUG_SESSION: Middleware Cookie SID: {sid}")
    session = None
    if sid:
        session = await Session.load(sid)
    
    if not session:
        # print("DEBUG_SESSION: Creating NEW Session")
        session = await Session.new()
    
    # Check Lang from Cookie if not in context
    if 'lang' not in session.context:
        # TODO: Get from browser Accept-Language or Cookie
        pass
        
    return session
