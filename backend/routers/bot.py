from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Job
from backend.schemas import BotStartPayload, BotAnswerPayload
from backend.bot import engine
from backend.bot import popup_manager

router = APIRouter(prefix="/api/bot", tags=["Bot Engine"])

@router.get("/status")
def get_bot_status(db: Session = Depends(get_db)):
    """
    Returns current bot machine state, active session stats, and active job details.
    """
    current_job = None
    if engine.current_job_id:
        current_job = db.query(Job).filter(Job.id == engine.current_job_id).first()
        
    return {
        "status": engine.status,
        "session_id": engine.session_id,
        "mode": engine.mode,
        "stats": engine.get_global_stats(),
        "current_job": current_job,
        "active_popup": popup_manager.active_popup
    }

@router.post("/start")
async def start_bot_session(payload: BotStartPayload, db: Session = Depends(get_db)):
    if engine.status not in ["idle", "stopped", "finished"]:
        raise HTTPException(status_code=400, detail="A bot session is already running.")
    
    # Handle list of search IDs or single fallback
    search_ids = payload.search_ids
    if not search_ids and payload.search_id is not None:
        search_ids = [payload.search_id]
        
    message = engine.start_bot(search_ids, payload.mode)
    return {"message": message}

@router.post("/pause")
async def pause_bot_session():
    message = engine.pause_bot()
    return {"message": message}

@router.post("/resume")
async def resume_bot_session():
    message = engine.resume_bot()
    return {"message": message}

@router.post("/stop")
async def stop_bot_session():
    message = engine.stop_bot()
    return {"message": message}

@router.post("/answer")
async def answer_bot_popup(payload: BotAnswerPayload):
    """
    Resolves the active blocking popup with the user response.
    """
    if not popup_manager.active_popup:
        raise HTTPException(status_code=400, detail="No active popup requires answering.")
    if popup_manager.active_popup.get("popup_id") != payload.popup_id:
        raise HTTPException(status_code=400, detail="Mismatching popup transactions.")
        
    await popup_manager.resolve_popup(payload.answer, payload.save)
    return {"message": "Popup resolved."}

@router.post("/skip-job")
async def skip_current_job():
    """
    Alternate response to skip the current job during blocking popups.
    """
    if not popup_manager.active_popup:
        raise HTTPException(status_code=400, detail="No active job popup requires resolution.")
    await popup_manager.resolve_popup("__skip_job__", False)
    return {"message": "Signal sent to skip active job."}

@router.post("/shutdown")
async def shutdown_application():
    """
    Gracefully stops the bot session, closes the playwright browser, and terminates the python server.
    """
    # 1. Stop the bot loop and clean up active popups
    try:
        engine.stop_bot()
    except Exception as e:
        print(f"Error stopping bot on shutdown: {e}")
        
    # 2. Force close browser context/session if active
    try:
        if engine.browser_session:
            await engine.browser_session.close()
            engine.browser_session = None
    except Exception as e:
        print(f"Error closing browser session: {e}")

    # 3. Schedule shutdown task to let the response complete first
    import asyncio
    import os
    import signal
    
    async def kill_later():
        await asyncio.sleep(0.5)
        # Send SIGINT to trigger uvicorn graceful shutdown
        os.kill(os.getpid(), signal.SIGINT)
        # Fallback to force exit after 2 seconds if still running
        await asyncio.sleep(2.0)
        os._exit(0)
        
    asyncio.create_task(kill_later())
    return {"message": "Application is shutting down..."}

