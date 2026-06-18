import asyncio
import uuid
from typing import Optional, Tuple, Any
from backend.services.logger import manager

# Active popup global state
active_popup: Optional[dict] = None
popup_response_event = asyncio.Event()
popup_response_value: Any = None
popup_response_save: bool = True

active_subprocess: Optional[asyncio.subprocess.Process] = None

def close_active_popups():
    global active_subprocess
    if active_subprocess and active_subprocess.returncode is None:
        try:
            active_subprocess.terminate()
        except Exception:
            pass
    try:
        from backend.bot.desktop_popup import close_active_root
        close_active_root()
    except Exception:
        pass

async def show_popup(popup_payload: dict) -> Tuple[Any, bool]:
    """
    Broadcasts a popup to the React frontend, pauses bot execution,
    and blocks until the user replies.
    """
    global active_popup, popup_response_value, popup_response_save, active_subprocess
    
    # Generate unique ID for this popup transaction if not present
    popup_id = popup_payload.get("popup_id") or str(uuid.uuid4())
    popup_payload["popup_id"] = popup_id
    
    # Increment popup statistics on start of popup display
    from backend.bot import engine
    try:
        engine.stats["popups"] += 1
        await engine.broadcast_status()
    except Exception:
        pass

    # Read popup_mode from settings
    from backend.database import SessionLocal
    from backend.models import Setting
    db = SessionLocal()
    popup_mode = "web"
    try:
        setting_val = db.query(Setting).filter(Setting.key == "popup_mode").first()
        if setting_val:
            popup_mode = setting_val.value
    except Exception:
        pass
    finally:
        db.close()

    if popup_mode == "desktop":
        import os
        import sys
        import json
        proc = None
        try:
            # Run the desktop popup as a separate process to guarantee Tkinter runs on its main thread
            # and gets foreground focus on the desktop.
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "backend.bot.desktop_popup",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=root_dir
            )
            active_subprocess = proc
            stdout, stderr = await proc.communicate(input=json.dumps(popup_payload).encode('utf-8'))
            
            if proc.returncode == 0:
                result = json.loads(stdout.decode('utf-8').strip())
                if "error" in result:
                    raise Exception(result["error"])
                return result.get("answer"), result.get("save", True)
            else:
                err_msg = stderr.decode('utf-8').strip()
                raise Exception(f"Popup process exited with code {proc.returncode}: {err_msg}")
        except asyncio.CancelledError:
            if proc and proc.returncode is None:
                try:
                    proc.terminate()
                    await proc.wait()
                except Exception:
                    pass
            raise
        except Exception as e:
            # Fallback to the thread implementation as a safety measure
            from backend.services.logger import log_event
            log_event(popup_payload.get("session_id", "system"), "error", "system", f"Failed running desktop popup process: {str(e)}. Falling back to in-process thread.")
            from backend.bot.desktop_popup import show_desktop_popup
            try:
                answer, save = await asyncio.to_thread(show_desktop_popup, popup_payload)
                return answer, save
            except asyncio.CancelledError:
                from backend.bot.desktop_popup import close_active_root
                close_active_root()
                raise
        finally:
            if active_subprocess == proc:
                active_subprocess = None

    active_popup = popup_payload
    popup_response_value = None
    popup_response_save = True
    popup_response_event.clear()
    
    # Broadcast to WebSocket client
    await manager.broadcast({
        "type": "popup",
        "payload": popup_payload
    })
    
    try:
        # Wait for frontend response
        await popup_response_event.wait()
        return popup_response_value, popup_response_save
    finally:
        active_popup = None
        try:
            await manager.broadcast({
                "type": "popup_close",
                "payload": {"popup_id": popup_id}
            })
        except Exception:
            pass

async def resolve_popup(answer: Any, save: bool = True):
    """
    Registers the response, clears the active popup state,
    and signals the waiting bot loop to resume.
    """
    global active_popup, popup_response_value, popup_response_save
    
    if not active_popup:
        return
        
    popup_id = active_popup["popup_id"]
    popup_response_value = answer
    popup_response_save = save
    active_popup = None
    popup_response_event.set()
    
    # Close popup on the frontend
    await manager.broadcast({
        "type": "popup_close",
        "payload": {"popup_id": popup_id}
    })

async def handle_client_websocket_message(data: dict):
    """
    Processes incoming messages sent by the frontend clients over the WebSocket.
    """
    msg_type = data.get("type")
    payload = data.get("payload", {})
    
    if msg_type == "answer_popup":
        answer = payload.get("answer")
        save = payload.get("save", True)
        await resolve_popup(answer, save)
    elif msg_type == "skip_job":
        # Special value to denote skipping the active job
        await resolve_popup("__skip_job__", False)
    elif msg_type == "close_popup":
        # Special value to denote closing the popup without skipping
        await resolve_popup("__close_popup__", False)
    elif msg_type == "manual_done":
        # Resumes a manual action popup (like login or captcha verification)
        await resolve_popup(True, False)
