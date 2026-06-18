import csv
import io
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from fastapi.responses import StreamingResponse
from backend.database import get_db
from backend.models import LogEntry, Session as SessionModel
from backend.schemas import LogEntryResponse, SessionResponse

router = APIRouter(prefix="/api/logs", tags=["Logs & Sessions"])

@router.get("", response_model=List[LogEntryResponse])
def list_logs(
    level: Optional[str] = None,
    category: Optional[str] = None,
    session_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(LogEntry)
    if level:
        query = query.filter(LogEntry.level == level)
    if category:
        query = query.filter(LogEntry.category == category)
    if session_id:
        query = query.filter(LogEntry.session_id == session_id)
        
    offset = (page - 1) * limit
    return query.order_by(LogEntry.timestamp.desc()).offset(offset).limit(limit).all()

@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(SessionModel).order_by(SessionModel.started_at.desc()).all()

@router.get("/export")
def export_logs(
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(LogEntry)
    if session_id:
        query = query.filter(LogEntry.session_id == session_id)
        
    logs = query.order_by(LogEntry.timestamp.asc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "session_id", "timestamp", "level", "category", "message", "company", "job_title", "job_url", "extra"])
    
    for log in logs:
        writer.writerow([
            log.id,
            log.session_id,
            log.timestamp.isoformat() + "Z",
            log.level,
            log.category,
            log.message,
            log.company or "",
            log.job_title or "",
            log.job_url or "",
            str(log.extra)
        ])
        
    output.seek(0)
    filename = f"logs_{session_id}.csv" if session_id else "all_logs.csv"
    
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response

@router.post("/open-window")
def open_log_window(session_id: Optional[str] = None):
    import subprocess
    import sys
    import os
    from fastapi import HTTPException
    
    try:
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        cmd = [sys.executable, "-m", "backend.bot.log_window"]
        if session_id:
            cmd.extend(["--session-id", session_id])
            
        subprocess.Popen(
            cmd,
            cwd=root_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return {"success": True, "message": "Log window opened"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open log window: {str(e)}")

