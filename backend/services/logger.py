import datetime
import asyncio
from typing import List, Optional
from fastapi import WebSocket
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import LogEntry

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        # Create a list of tasks to run parallel sends
        if not self.active_connections:
            return
        
        # Clean up dead connections during iteration
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
                
        for dead in dead_connections:
            self.disconnect(dead)

# Global connection manager instance
manager = ConnectionManager()

def log_event(
    session_id: str,
    level: str,          # success | info | warning | error | action | debug
    category: str,       # auth | search | apply | qa | bot | system
    message: str,
    company: Optional[str] = None,
    job_title: Optional[str] = None,
    job_url: Optional[str] = None,
    job_id: Optional[int] = None,
    extra: Optional[dict] = None
) -> LogEntry:
    """
    Saves a log entry to the SQLite database and broadcasts it to the frontend via WebSockets.
    """
    db = SessionLocal()
    try:
        log_entry = LogEntry(
            session_id=session_id,
            timestamp=datetime.datetime.utcnow(),
            level=level,
            category=category,
            message=message,
            company=company,
            job_title=job_title,
            job_url=job_url,
            job_id=job_id,
            extra=extra or {}
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        
        # Prepare WebSocket payload
        payload = {
            "type": "log_entry",
            "payload": {
                "id": log_entry.id,
                "session_id": log_entry.session_id,
                "timestamp": log_entry.timestamp.isoformat() + "Z",
                "level": log_entry.level,
                "category": log_entry.category,
                "message": log_entry.message,
                "company": log_entry.company,
                "job_title": log_entry.job_title,
                "job_url": log_entry.job_url,
                "job_id": log_entry.job_id,
                "extra": log_entry.extra
            }
        }
        
        # Broadcast asynchronously if event loop is running
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(payload))
        except Exception:
            pass
            
        return log_entry
    finally:
        db.close()
