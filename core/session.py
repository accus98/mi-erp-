import uuid
import os
from fastapi import Request
from core.cache import Cache

# Async Session Logic
class Session:
    def __init__(self, sid):
        self.sid = sid
        self.uid = None
        self.login = None
        self.context = {}
        self._dirty = False 
        
    @classmethod
    def new(cls):
        sid = str(uuid.uuid4())
        sess = cls(sid)
        sess.csrf_token = str(uuid.uuid4()) # Generate CSRF Token
        sess.save()
        return sess

    @classmethod
    def load(cls, sid):
        # print(f"DEBUG_SESSION: Loading {sid}")
        data = Cache.get(f"session:{sid}")
        # print(f"DEBUG_SESSION: Data for {sid}: {data}")
        if data:
            sess = cls(sid)
            sess.uid = data.get('uid')
            sess.login = data.get('login')
            sess.context = data.get('context', {})
            sess.csrf_token = data.get('csrf_token') or str(uuid.uuid4()) # Auto-heal if missing
            return sess
        return None

    def rotate(self):
        """
        Regenerate Session ID to prevent Fixation Attacks.
        """
        old_sid = self.sid
        # Create new ID
        self.sid = str(uuid.uuid4())
        self.csrf_token = str(uuid.uuid4()) # Rotate CSRF
        # Save new
        self.save()
        # Delete old
        Cache.delete(f"session:{old_sid}")
        # print(f"DEBUG_SESSION: Rotated {old_sid} -> {self.sid}")

    def save(self):
        data = {
            'uid': self.uid,
            'login': self.login,
            'context': self.context,
            'csrf_token': getattr(self, 'csrf_token', None)
        }
        # TTL 1 day
        Cache.set(f"session:{self.sid}", data, ttl=86400)


# Dependency for Session
async def get_session(request: Request):
    sid = request.cookies.get('session_id')
    # print(f"DEBUG_SESSION: Middleware Cookie SID: {sid}")
    session = None
    if sid:
        session = Session.load(sid)
    
    if not session:
        # print("DEBUG_SESSION: Creating NEW Session")
        session = Session.new()
    
    # Check Lang from Cookie if not in context
    if 'lang' not in session.context:
        # TODO: Get from browser Accept-Language or Cookie
        pass
        
    return session
