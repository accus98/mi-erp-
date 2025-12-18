
from fastapi import WebSocket
from typing import List
import json
import logging

logger = logging.getLogger(__name__)

class NotificationBus:
    def __init__(self):
        self.connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        logger.info(f"WebSocket Client connected. Active: {len(self.connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
            logger.info(f"WebSocket Client disconnected. Active: {len(self.connections)}")

    async def broadcast(self, message: dict):
        """
        Send a message to all connected clients.
        """
        payload = json.dumps(message)
        dead_connections = []
        
        for connection in list(self.connections):
            try:
                # Direct send of text (JSON)
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                dead_connections.append(connection)
                
        for dead in dead_connections:
            self.disconnect(dead)

# Global Instance
bus = NotificationBus()
