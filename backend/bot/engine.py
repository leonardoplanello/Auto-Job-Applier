import os
import asyncio
import re
import datetime
import random
import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from playwright.async_api import Page, Locator

from backend.database import SessionLocal, DATA_DIR
from backend.models import Job, SearchCriteria, Application, Session as SessionModel, Setting, Profile, RecruiterContact, ContactLog, MessageTemplate
from backend.bot.session_manager import BrowserSession
from backend.bot.job_discovery import discover_jobs
from backend.bot.form_parser import parse_form, FormField, FieldType, is_placeholder_value
from backend.bot.qa_resolver import resolve_field_value, SkipJobException, BrowserClosedException, is_browser_closed_exception, StopBotException, ClosePopupException
from backend.bot.popup_manager import show_popup
from backend.services.logger import log_event, manager

# Global active bot state
session_id: Optional[str] = None
status: str = "idle"               # idle | running | paused | waiting_user | stopped | finished
previous_status: str = "running"
mode: str = "review"               # review | auto (active execution mode)
current_job_id: Optional[int] = None
current_job_task: Optional[asyncio.Task] = None
active_page: Optional[Page] = None
stats: Dict[str, int] = {"found": 0, "applied": 0, "skipped": 0, "failed": 0, "popups": 0}
historical_stats: Optional[Dict[str, int]] = None

class LinkedInLimitReachedException(Exception):
    """
    Raised when LinkedIn Easy Apply daily application limit is encountered.
    """
    pass

async def check_linkedin_limit(page: Page) -> bool:
    """
    Scans the page body text and specific elements for indicators that
    the daily LinkedIn Easy Apply limit has been reached.
    """
    try:
        body_text = await page.evaluate("() => document.body.textContent || ''")
        normalized_body = body_text.replace("’", "'").lower()
        if "you reached today's easy apply limit" in normalized_body:
            return True
        if "we limit easy apply submissions" in normalized_body:
            return True
            
        texts_to_check = [
            "You reached today’s Easy Apply limit",
            "You reached today's Easy Apply limit",
            "We limit Easy Apply submissions"
        ]
        for text in texts_to_check:
            loc = page.get_by_text(text)
            if await loc.count() > 0:
                for i in range(await loc.count()):
                    try:
                        if await loc.nth(i).is_visible():
                            return True
                    except Exception:
                        pass
    except Exception:
        pass
    return False

def get_global_stats() -> Dict[str, int]:
    global historical_stats
    db = SessionLocal()
    try:
        from sqlalchemy import func
        from backend.models import Job, Session as SessionModel
        
        found = db.query(Job).count()
        applied = db.query(Job).filter(Job.status == "applied").count()
        skipped = db.query(Job).filter(Job.status == "skipped").count()
        failed = db.query(Job).filter(Job.status == "failed").count()
        
        # Popups count can remain from session + historical
        popups_result = db.query(func.sum(SessionModel.popups_shown)).scalar()
        popups = (popups_result or 0) + stats.get("popups", 0)
        
        return {
            "found": found,
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "popups": popups
        }
    finally:
        db.close()

browser_session: Optional[BrowserSession] = None
bot_task: Optional[asyncio.Task] = None
pause_event = asyncio.Event()
pause_event.set()  # Unpaused by default

def parse_job_details_from_title(page_title: str) -> tuple[Optional[str], Optional[str]]:
    if not page_title:
        return None, None
    
    cleaned = page_title
    for suffix in [" | LinkedIn", " | linkedin", " - LinkedIn", " - linkedin"]:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)]
    cleaned = cleaned.strip()
    
    # Format 1: Company hiring Job Title in Location
    if " hiring " in cleaned:
        parts = cleaned.split(" hiring ", 1)
        company = parts[0].strip()
        rest = parts[1].strip()
        if " in " in rest:
            job_title = rest.split(" in ", 1)[0].strip()
        else:
            job_title = rest
        return job_title, company
        
    # Format 2: Job Title | Company
    if " | " in cleaned:
        parts = [p.strip() for p in cleaned.split(" | ")]
        if len(parts) >= 2:
            return parts[0], parts[1]
            
    # Format 3: Job Title at Company
    if " at " in cleaned:
        parts = cleaned.split(" at ", 1)
        return parts[0].strip(), parts[1].strip()
        
    return None, None


def extract_job_id_from_url(url: str) -> Optional[str]:
    # Look for /view/(\d+)
    view_match = re.search(r'/view/(\d+)', url)
    if view_match:
        return view_match.group(1)
    # Look for currentJobId=(\d+)
    param_match = re.search(r'[?&]currentJobId=(\d+)', url)
    if param_match:
        return param_match.group(1)
    return None


async def broadcast_status():
    """
    Broadcasts the active bot status to all WebSocket clients.
    """
    current_job_obj = None
    if current_job_id:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == current_job_id).first()
            if job:
                current_job_obj = {
                    "id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "remote": job.remote,
                    "status": job.status,
                    "description": job.description,
                    "url": job.url,
                    "linkedin_id": job.linkedin_id,
                    "easy_apply": job.easy_apply,
                    "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
                    "skip_reason": job.skip_reason,
                    "priority": job.priority
                }
        finally:
            db.close()

    await manager.broadcast({
        "type": "bot_status",
        "payload": {
            "session_id": session_id,
            "status": status,
            "mode": mode,
            "current_job": current_job_obj,
            "stats": get_global_stats()
        }
    })

async def update_status(new_status: str):
    global status, previous_status
    if status == "paused" and new_status not in ["stopped", "finished"]:
        previous_status = new_status
        return
    status = new_status
    
    # Save status to SQLite Session record if active
    if session_id:
        db = SessionLocal()
        try:
            sess = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            if sess:
                old_status = sess.status
                sess.status = new_status
                if new_status in ["stopped", "finished"] and old_status not in ["stopped", "finished"]:
                    sess.ended_at = datetime.datetime.utcnow()
                    sess.jobs_found = stats["found"]
                    sess.jobs_applied = stats["applied"]
                    sess.jobs_skipped = stats["skipped"]
                    sess.jobs_failed = stats["failed"]
                    sess.popups_shown = stats["popups"]
                    
                    if historical_stats is not None:
                        historical_stats["found"] += stats["found"]
                        historical_stats["applied"] += stats["applied"]
                        historical_stats["skipped"] += stats["skipped"]
                        historical_stats["failed"] += stats["failed"]
                        historical_stats["popups"] += stats["popups"]
                db.commit()
        finally:
            db.close()
            
    await broadcast_status()

async def human_delay(min_ms: int = 800, max_ms: int = 3000):
    """
    Simulates human delay using a Gaussian distribution centered between min and max bounds.
    """
    mid = (min_ms + max_ms) / 2
    std = (max_ms - min_ms) / 6
    ms = random.gauss(mid, std)
    ms = max(min_ms, min(max_ms, ms))
    await asyncio.sleep(ms / 1000.0)

async def type_human(locator: Locator, text: str):
    """
    Types text character-by-character with randomized pauses to simulate human keypresses.
    Includes a 10% chance of a backspace error correction simulation.
    """
    await locator.focus()
    # Clear existing content
    await locator.click()
    await locator.press("Control+A")
    await locator.press("Backspace")
    
    text_str = str(text)
    for char in text_str:
        await locator.type(char)
        await asyncio.sleep(random.uniform(0.04, 0.15))
        
    # 10% chance to simulate minor typo correction
    if len(text_str) > 2 and random.random() < 0.1:
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await locator.press("Backspace")
        await asyncio.sleep(random.uniform(0.2, 0.4))
        await locator.type(text_str[-1])
        
    await locator.press("Tab")

async def select_option_human(page: Page, field: FormField, option_text: str):
    """
    Selects dropdown options for standard Select controls or custom comboboxes.
    """
    locator = page.locator(field.selector).first
    
    # 1. Native HTML Select Element
    if field.field_type == FieldType.SELECT and "select" in field.selector:
        await locator.select_option(label=option_text)
        return

    # 2. Custom Combobox Dropdown Trigger
    await locator.click()
    await page.wait_for_timeout(random.randint(600, 1200))
    
    # Check if option elements are loaded in DOM (e.g. role="option" or search-results lists)
    # Search for an element containing the exact option text
    options_selector = f"[role='option'] >> text='{option_text}'"
    opt_loc = page.locator(options_selector).first
    
    if await opt_loc.count() > 0:
        await opt_loc.click()
    else:
        # Fallback: type the answer and hit Enter
        await page.keyboard.type(option_text)
        await page.wait_for_timeout(random.randint(500, 900))
        await page.keyboard.press("ArrowDown")
        await page.wait_for_timeout(200)
        await page.keyboard.press("Enter")

async def fill_field(page: Page, field: FormField, value: Any):
    """
    Dispatches input values to DOM nodes based on their FieldType.
    """
    locator = page.locator(field.selector).first
    
    if field.field_type in [FieldType.TEXT, FieldType.TEXTAREA]:
        await type_human(locator, str(value))
    elif field.field_type == FieldType.NUMBER:
        await type_human(locator, str(value))
    elif field.field_type == FieldType.FILE:
        # Value contains local absolute path to resume PDF
        if value:
            if os.path.exists(value):
                await locator.set_input_files(value)
            else:
                from backend.services.logger import log_event
                from backend.bot import engine
                log_event(engine.session_id or "system", "warning", "apply", f"File '{value}' not found on local disk. Skipping file input upload.")
    elif field.field_type in [FieldType.SELECT]:
        await select_option_human(page, field, str(value))
    elif field.field_type == FieldType.RADIO:
        # We need to find the specific radio option in this radio group/section
        # value is the option text we want to select (e.g., "Yes" or "No")
        clicked = False
        target_value = str(value).strip().lower()
        container = None
        
        # 1. Try to find the radio group inputs using field.selector
        radio_inputs = []
        if field.selector:
            radio_inputs = await page.locator(field.selector).all()
        
        # If we got 0 or 1 radio input, we need to find the full group/section
        if len(radio_inputs) <= 1:
            first_input = page.locator(field.selector).first
            if await first_input.count() > 0:
                # Walk up ancestors (up to 5 levels) to find a container that has multiple radios
                curr_loc = first_input
                for _ in range(5):
                    curr_loc = curr_loc.locator("xpath=..")
                    if await curr_loc.count() > 0:
                        radios_count = await curr_loc.locator("input[type='radio']").count()
                        if radios_count > 1:
                            container = curr_loc
                            break
        
        # If that failed, try finding the container by matching field.label text
        if (not container or await container.count() == 0) and field.label:
            # Scrape all label/legend elements to find the one matching field.label
            label_locs = page.locator("legend, label, span, h3")
            for i in range(await label_locs.count()):
                loc = label_locs.nth(i)
                text = await loc.inner_text()
                if field.label.lower() in text.lower():
                    # Walk up ancestors (up to 5 levels) to find a container that has multiple radios
                    curr_loc = loc
                    for _ in range(5):
                        curr_loc = curr_loc.locator("xpath=..")
                        if await curr_loc.count() > 0:
                            radios_count = await curr_loc.locator("input[type='radio']").count()
                            if radios_count > 1:
                                container = curr_loc
                                break
                    if container:
                        break
        
        # If we found a container, get all radio inputs inside it
        if container and await container.count() > 0:
            radio_inputs = await container.locator("input[type='radio']").all()
        
        # 2. Iterate through candidate radios and check for label or value match
        for r in radio_inputs:
            opt_label_text = ""
            
            # Try finding label in the same parent container
            parent = r.locator("xpath=..")
            lbl = parent.locator("label").first
            if await lbl.count() > 0:
                opt_label_text = await lbl.inner_text()
            
            # Fallback 1: check for 'for' attribute matching id
            r_id = await r.get_attribute("id")
            if not opt_label_text.strip() and r_id:
                lbl = page.locator(f"label[for='{r_id}']").first
                if await lbl.count() > 0:
                    opt_label_text = await lbl.inner_text()
            
            # Fallback 2: parent label
            if not opt_label_text.strip():
                parent_label = r.locator("xpath=ancestor::label").first
                if await parent_label.count() > 0:
                    opt_label_text = await parent_label.inner_text()
            
            # Fallback 3: sibling label
            if not opt_label_text.strip():
                lbl_sibling = r.locator("xpath=following-sibling::label").first
                if await lbl_sibling.count() > 0:
                    opt_label_text = await lbl_sibling.inner_text()
                    
            opt_label_text = opt_label_text.strip()
            r_val = (await r.get_attribute("value") or "").strip()
            
            if opt_label_text.lower() == target_value or r_val.lower() == target_value:
                # We found the matching radio option! Let's select it.
                # A. Programmatically check the input directly
                try:
                    await r.check(force=True)
                except Exception:
                    pass
                
                # B. Click the input directly to fire click events
                try:
                    await r.click(force=True)
                except Exception:
                    pass
                
                # C. Click label to fire custom JS click listeners and update UI styles
                label_clicked = False
                
                # Try sibling label
                try:
                    lbl_sibling = r.locator("xpath=following-sibling::label").first
                    if await lbl_sibling.count() > 0:
                        await lbl_sibling.click(force=True)
                        label_clicked = True
                except Exception:
                    pass
                
                # Try parent container label
                if not label_clicked:
                    try:
                        parent = r.locator("xpath=..")
                        lbl = parent.locator("label").first
                        if await lbl.count() > 0:
                            await lbl.click(force=True)
                            label_clicked = True
                    except Exception:
                        pass
                
                # Try label matching id
                if not label_clicked and r_id:
                    try:
                        lbl = page.locator(f"label[for='{r_id}']").first
                        if await lbl.count() > 0:
                            await lbl.click(force=True)
                            label_clicked = True
                    except Exception:
                        pass
                
                # Try parent label
                if not label_clicked:
                    try:
                        parent_label = r.locator("xpath=ancestor::label").first
                        if await parent_label.count() > 0:
                            await parent_label.click(force=True)
                            label_clicked = True
                    except Exception:
                        pass
                
                clicked = True
                break
                
        # 3. Fallbacks
        if not clicked:
            # Fallback A: Inside the container (if found), find any label containing value
            if field.label:
                try:
                    container = page.locator(f"fieldset:has(legend:has-text('{field.label}')), div:has(label:has-text('{field.label}'))").first
                    if await container.count() > 0:
                        lbl = container.locator(f"label:has-text('{value}')").first
                        if await lbl.count() > 0:
                            await lbl.click(force=True)
                            clicked = True
                except Exception:
                    pass
            
            # Fallback B: Global search (original behavior)
            if not clicked:
                try:
                    option_loc = page.locator(f"label:has-text('{value}')").first
                    if await option_loc.count() > 0:
                        await option_loc.click(force=True)
                        clicked = True
                except Exception:
                    pass
                
                if not clicked:
                    try:
                        direct_loc = page.locator(f"input[type='radio'][value='{value}']").first
                        if await direct_loc.count() > 0:
                            await direct_loc.check(force=True)
                            clicked = True
                    except Exception:
                        pass
    elif field.field_type == FieldType.CHECKBOX:
        # Check if it is a checklist of multiple options (meaning options is not empty)
        if field.options:
            # Multi-select checkbox group!
            import json
            selected_options = []
            if isinstance(value, list):
                selected_options = [str(v).strip().lower() for v in value]
            elif isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        selected_options = [str(v).strip().lower() for v in parsed]
                    else:
                        selected_options = [str(parsed).strip().lower()]
                except json.JSONDecodeError:
                    if value.startswith("[") and value.endswith("]"):
                        items = value[1:-1].split(",")
                        for item in items:
                            item = item.strip().strip("'\"")
                            if item:
                                selected_options.append(item.lower())
                    else:
                        selected_options = [v.strip().lower() for v in value.split(",") if v.strip()]
            else:
                selected_options = [str(value).strip().lower()]

            # 1. Walk up to container or locate by field.selector
            container = None
            checkbox_inputs = []
            if field.selector:
                checkbox_inputs = await page.locator(field.selector).all()
            
            # If we got 0 or 1 input, walk up ancestors to find a container with multiple checkboxes
            if len(checkbox_inputs) <= 1:
                first_input = page.locator(field.selector).first
                if await first_input.count() > 0:
                    curr_loc = first_input
                    for _ in range(5):
                        curr_loc = curr_loc.locator("xpath=..")
                        if await curr_loc.count() > 0:
                            cb_count = await curr_loc.locator("input[type='checkbox']").count()
                            if cb_count > 1:
                                container = curr_loc
                                break
                                
            # If that failed, try matching by field.label
            if (not container or await container.count() == 0) and field.label:
                label_locs = page.locator("legend, label, span, h3")
                for i in range(await label_locs.count()):
                    loc = label_locs.nth(i)
                    text = await loc.inner_text()
                    if field.label.lower() in text.lower():
                        curr_loc = loc
                        for _ in range(5):
                            curr_loc = curr_loc.locator("xpath=..")
                            if await curr_loc.count() > 0:
                                cb_count = await curr_loc.locator("input[type='checkbox']").count()
                                if cb_count > 1:
                                    container = curr_loc
                                    break
                        if container:
                            break
                            
            if container and await container.count() > 0:
                checkbox_inputs = await container.locator("input[type='checkbox']").all()

            # Now check/uncheck each checkbox depending on if its label matches selected_options
            for cb in checkbox_inputs:
                opt_label_text = ""
                
                parent = cb.locator("xpath=..")
                lbl = parent.locator("label").first
                if await lbl.count() > 0:
                    opt_label_text = await lbl.inner_text()
                
                cb_id = await cb.get_attribute("id")
                if not opt_label_text.strip() and cb_id:
                    lbl = page.locator(f"label[for='{cb_id}']").first
                    if await lbl.count() > 0:
                        opt_label_text = await lbl.inner_text()
                
                if not opt_label_text.strip():
                    parent_label = cb.locator("xpath=ancestor::label").first
                    if await parent_label.count() > 0:
                        opt_label_text = await parent_label.inner_text()
                
                if not opt_label_text.strip():
                    lbl_sibling = cb.locator("xpath=following-sibling::label").first
                    if await lbl_sibling.count() > 0:
                        opt_label_text = await lbl_sibling.inner_text()
                        
                opt_label_text = opt_label_text.strip().lower()
                
                should_check = False
                for sel_opt in selected_options:
                    if sel_opt == opt_label_text or sel_opt in opt_label_text or opt_label_text in sel_opt:
                        should_check = True
                        break
                        
                if should_check:
                    if not await cb.is_checked():
                        try:
                            await cb.check(force=True)
                        except Exception:
                            try:
                                await cb.click(force=True)
                            except Exception:
                                pass
                else:
                    if await cb.is_checked():
                        try:
                            await cb.uncheck(force=True)
                        except Exception:
                            try:
                                await cb.click(force=True)
                            except Exception:
                                pass
        else:
            # Check if value equals positive yes/true options
            is_positive = str(value).lower() in ["yes", "sim", "true", "1", "y", "t", "checked"]
            if is_positive:
                if not await locator.is_checked():
                    try:
                        await locator.check(force=True)
                    except Exception:
                        try:
                            await locator.click(force=True)
                        except Exception:
                            pass
                    # Fallback: try clicking the associated label if not checked
                    if not await locator.is_checked():
                        try:
                            cb_id = await locator.get_attribute("id")
                            label_clicked = False
                            if cb_id:
                                label_loc = page.locator(f"label[for='{cb_id}']").first
                                if await label_loc.count() > 0:
                                    await label_loc.click(force=True)
                                    label_clicked = True
                            if not label_clicked:
                                parent_label = locator.locator("xpath=ancestor::label").first
                                if await parent_label.count() > 0:
                                    await parent_label.click(force=True)
                                    label_clicked = True
                            if not label_clicked:
                                for sibling_xpath in ["xpath=following-sibling::label", "xpath=preceding-sibling::label"]:
                                    sib = locator.locator(sibling_xpath).first
                                    if await sib.count() > 0:
                                        await sib.click(force=True)
                                        break
                        except Exception:
                            pass
            else:
                if await locator.is_checked():
                    try:
                        await locator.uncheck(force=True)
                    except Exception:
                        try:
                            await locator.click(force=True)
                        except Exception:
                            pass
                    # Fallback: try clicking the associated label if still checked
                    if await locator.is_checked():
                        try:
                            cb_id = await locator.get_attribute("id")
                            label_clicked = False
                            if cb_id:
                                label_loc = page.locator(f"label[for='{cb_id}']").first
                                if await label_loc.count() > 0:
                                    await label_loc.click(force=True)
                                    label_clicked = True
                            if not label_clicked:
                                parent_label = locator.locator("xpath=ancestor::label").first
                                if await parent_label.count() > 0:
                                    await parent_label.click(force=True)
                                    label_clicked = True
                            if not label_clicked:
                                for sibling_xpath in ["xpath=following-sibling::label", "xpath=preceding-sibling::label"]:
                                    sib = locator.locator(sibling_xpath).first
                                    if await sib.count() > 0:
                                        await sib.click(force=True)
                                        break
                        except Exception:
                            pass

async def check_auth(page: Page, session_id: str, force_navigate: bool = True) -> bool:
    """
    Verifies if the loaded session is already logged into LinkedIn.
    """
    if force_navigate:
        try:
            # Navigating to /feed/ will redirect guests to the login page
            await page.goto("https://www.linkedin.com/feed/")
            await page.wait_for_timeout(random.randint(2000, 3500))
        except Exception:
            pass
            
    current_url = page.url.lower()

    # 1. URL Check
    # Verify we are on a page that is normally only accessible when logged in,
    # and not redirected to a sign-in or guest page.
    if "/feed" in current_url or "/jobs" in current_url or "/mynetwork" in current_url:
        if "/login" not in current_url and "/signup" not in current_url and "/checkpoint" not in current_url:
            return True

    # 2. Profile Selector Check (Fallback indicator in DOM)
    try:
        profile_indicator = page.locator("a.global-nav__primary-link[href*='/me/'], .global-nav__me-photo, button.global-nav__primary-link-me-menu-trigger, img.global-nav__me-photo")
        if await profile_indicator.count() > 0:
            return True
    except Exception:
        pass
        
    return False


def is_applied_text(txt: str) -> bool:
    """
    Checks if the given text indicates that the job has already been applied to,
    while carefully ignoring applicant counts (e.g. '40 applied', '50 candidaturas', etc.)
    and other general alert phrases.
    """
    import re
    txt = txt.lower().strip()
    
    # 1. Ignore if it matches applicant count patterns (e.g. '50 applied', 'over 200 applied', '1 applied')
    if re.search(r'^(over\s+)?\d+\s+applied$', txt):
        return False
        
    # 2. Ignore general negative keywords (e.g. plural applicants/candidatures/solicitudes)
    if any(neg in txt for neg in ["people", "candidatos", "candidaturas", "applicants", "pessoas", "solicitudes", "inscrits", "candidatures"]):
        return False
        
    # 3. Check for specific verbs or past-participles that mean "applied"
    applied_keywords = [
        "candidatou",            # Portuguese: "candidatou-se"
        "candidatura enviada",   # Portuguese: "candidatura enviada"
        "candidatura realizada", # Portuguese: "candidatura realizada"
        "candidatura submetida", # Portuguese: "candidatura submetida"
        "postulado",             # Spanish: "postulado"
        "postulada",             # Spanish: "postulada"
        "solicitud enviada",     # Spanish: "solicitud enviada"
        "solicitud presentada",  # Spanish: "solicitud presentada"
        "inscrit",               # French: "inscrit"
        "candidature envoyée",   # French: "candidature envoyée"
        "beworben",              # German: "beworben"
        "application submitted", # English: "application submitted"
    ]
    
    if any(kw in txt for kw in applied_keywords):
        return True
        
    # 4. Check for English "applied" keyword (ensuring it's not applicant count or UI options)
    if "applied" in txt:
        if not any(x in txt for x in ["filter", "compatible"]):
            # Ensure it doesn't look like an applicant count (e.g., "40 applied" or "10 applied")
            if not re.search(r'\d+\s+applied', txt):
                return True
                
    return False


async def check_if_already_applied(page: Page) -> bool:
    """
    Checks if the job on the page has already been applied to.
    """
    applied_indicators = [
        ".artdeco-inline-feedback",
        ".jobs-s-apply__applied-date",
        "span.artdeco-inline-feedback__message",
        "div.artdeco-inline-feedback",
        ".artdeco-inline-feedback--success",
        ".jobs-s-apply",
        ".jobs-applied-state-status",
        ".artdeco-toast-item",
        ".artdeco-notification"
    ]
    
    # 1. Check specific selectors
    for sel in applied_indicators:
        loc = page.locator(sel)
        try:
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible():
                    txt = await el.inner_text()
                    if is_applied_text(txt):
                        return True
        except Exception:
            pass

    # 2. Check text in main job containers
    container_selectors = [
        ".jobs-unified-top-card", 
        ".jobs-details", 
        ".jobs-search__job-details--container", 
        "div.jobs-details__main-content",
        "main", 
        "#main",
        "div.scaffold-layout__detail",
        ".jobs-box"
    ]
    for sel in container_selectors:
        loc = page.locator(sel)
        try:
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible():
                    text = await el.inner_text()
                    for line in text.split("\n"):
                        if is_applied_text(line):
                            return True
        except Exception:
            pass

    # 3. Check general text selectors on the page for common applied phrases
    common_applied_phrases = [
        "application submitted",
        "candidatura enviada",
        "candidatura realizada",
        "candidatura submetida",
        "solicitud enviada",
        "solicitud presentada",
        "candidature envoyée"
    ]
    for phrase in common_applied_phrases:
        try:
            loc = page.locator(f"text='{phrase}'")
            count = await loc.count()
            for i in range(count):
                if await loc.nth(i).is_visible():
                    return True
        except Exception:
            pass
            
    return False


async def check_if_no_longer_accepting(page: Page) -> bool:
    """
    Checks if the job is no longer accepting applications.
    """
    closed_phrases = [
        "no longer accepting applications",
        "não aceita mais candidaturas",
        "não estão mais aceitando candidaturas",
        "não está mais aceitando candidaturas",
        "ya no se aceptan solicitudes",
        "ya no acepta solicitudes",
        "n'accepte plus de candidatures",
        "nimmt keine bewerbungen mehr an",
        "no longer accepting"
    ]
    
    container_selectors = [
        ".artdeco-inline-feedback",
        ".jobs-unified-top-card", 
        ".jobs-details", 
        ".jobs-search__job-details--container", 
        "div.jobs-details__main-content",
        "main", 
        "#main",
        "div.scaffold-layout__detail",
        ".jobs-box"
    ]
    
    for sel in container_selectors:
        loc = page.locator(sel)
        try:
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                if await el.is_visible():
                    text = await el.inner_text()
                    text_lower = text.lower()
                    for phrase in closed_phrases:
                        if phrase in text_lower:
                            return True
        except Exception:
            pass
            
    return False


async def apply_to_job(
    page: Page,
    job: Job,
    session_id: str,
    db: Session,
    bot_settings: dict
) -> bool:
    """
    Orchestrates the entire Easy Apply application flow for a single Job.
    """
    global current_job_id
    current_job_id = job.id
    await broadcast_status()
    
    if page.is_closed():
        raise BrowserClosedException("Browser was closed.")
    
    # Query resume_path early so it is available for any Application entry creation
    profile = db.query(Profile).filter(Profile.id == 1).first()
    resume_path = profile.resume_path if profile else None

    # Check if already applied in DB
    existing_applied = db.query(Job).filter(Job.linkedin_id == job.linkedin_id, Job.status == "applied").first()
    if existing_applied or job.status == "applied":
        log_event(
            session_id, "info", "apply",
            f"Job already marked as applied in database. Skipping — {job.title} @ {job.company}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        
        # Ensure Application entry exists
        target_job = existing_applied if existing_applied else job
        existing_app = db.query(Application).filter(Application.job_id == target_job.id).first()
        if not existing_app:
            new_app = Application(
                job_id=target_job.id,
                status="submitted",
                fields_filled=[],
                resume_used=resume_path,
                submitted_at=datetime.datetime.utcnow()
            )
            db.add(new_app)
            db.commit()
            
        stats["skipped"] += 1
        return False

    log_event(
        session_id, "info", "apply",
        f"Starting application for {job.title} @ {job.company}",
        company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
    )
    
    # Navigate to Job Detail page
    try:
        await page.goto(job.url)
        await page.wait_for_timeout(random.randint(2500, 4000))
        if await check_linkedin_limit(page):
            raise LinkedInLimitReachedException()
    except Exception as e:
        if isinstance(e, LinkedInLimitReachedException):
            raise e
        if is_browser_closed_exception(e):
            raise BrowserClosedException("Browser was closed.") from e
        # Check if either Easy Apply or Already Applied is present despite the timeout
        easy_apply_selectors = [
            "button.jobs-apply-button",
            "button.jobs-apply-button--top-card",
            "button[class*='jobs-apply-button']",
            "button[class*='jobs-s-apply__button']",
            "button[aria-label*='Easy Apply']",
            "button[aria-label*='Candidatura simplificada']",
            "button[aria-label*='Candidatar-se facilmente']",
            "a[aria-label*='Easy Apply']",
            "a[aria-label*='Candidatura simplificada']",
            "a[aria-label*='Candidatar-se facilmente']",
            "a[href*='openSDUIApplyFlow=true']",
            "button:has-text('Easy Apply')",
            "button:has-text('Candidatura simplificada')",
            "button:has-text('Candidatar-se facilmente')",
            "button:has-text('Candidatar-se')",
            "a:has-text('Easy Apply')",
            "a:has-text('Candidatura simplificada')",
            "a:has-text('Candidatar-se facilmente')"
        ]
        easy_apply_selector = ", ".join(easy_apply_selectors)
        easy_apply_btn = page.locator(easy_apply_selector).first
        
        # Check applied indicators too
        already_applied_check = await check_if_already_applied(page)
        no_longer_accepting_check = await check_if_no_longer_accepting(page)
                
        if already_applied_check or no_longer_accepting_check or await easy_apply_btn.count() > 0:
            log_event(
                session_id, "warning", "apply",
                "Navigation to job detail page timed out, but page content is present. Proceeding...",
                company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
            )
        else:
            raise e

    # Check if we were redirected to a login or checkpoint page
    if "login" in page.url or "checkpoint" in page.url:
        log_event(
            session_id, "error", "auth",
            f"Redirected to login/checkpoint during apply for {job.title} @ {job.company}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        raise Exception("Session expired or security checkpoint triggered during application.")

    # Check if already applied on LinkedIn page (e.g. banner, message or button is not Easy Apply)
    already_applied = False
    no_longer_accepting = False
    easy_apply_selectors = [
        "button.jobs-apply-button",
        "button.jobs-apply-button--top-card",
        "button[class*='jobs-apply-button']",
        "button[class*='jobs-s-apply__button']",
        "button[aria-label*='Easy Apply']",
        "button[aria-label*='Candidatura simplificada']",
        "button[aria-label*='Candidatar-se facilmente']",
        "a[aria-label*='Easy Apply']",
        "a[aria-label*='Candidatura simplificada']",
        "a[aria-label*='Candidatar-se facilmente']",
        "a[href*='openSDUIApplyFlow=true']",
        "button:has-text('Easy Apply')",
        "button:has-text('Candidatura simplificada')",
        "button:has-text('Candidatar-se facilmente')",
        "button:has-text('Candidatar-se')",
        "a:has-text('Easy Apply')",
        "a:has-text('Candidatura simplificada')",
        "a:has-text('Candidatar-se facilmente')"
    ]
    easy_apply_selector = ", ".join(easy_apply_selectors)
    
    # We poll for up to 5 seconds to wait for page to render either the Easy Apply button or the applied indicator
    for _ in range(10):
        already_applied = await check_if_already_applied(page)
        if already_applied:
            break
            
        no_longer_accepting = await check_if_no_longer_accepting(page)
        if no_longer_accepting:
            break
            
        # Check if Easy Apply is visible
        easy_apply_btn = page.locator(easy_apply_selector).first
        try:
            if await easy_apply_btn.is_visible():
                break
        except Exception:
            pass
            
        await page.wait_for_timeout(500)

    if await check_linkedin_limit(page):
        raise LinkedInLimitReachedException()

    if no_longer_accepting:
        log_event(
            session_id, "info", "apply",
            f"Job is no longer accepting applications. Failing — {job.title} @ {job.company}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        job.status = "failed"
        job.skip_reason = "No longer accepting applications"
        db.commit()
        stats["failed"] += 1
        return False

    if already_applied:
        log_event(
            session_id, "info", "apply",
            f"Job already applied on LinkedIn. Skipping — {job.title} @ {job.company}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        job.status = "applied"
        db.commit()
        
        # Ensure Application entry exists
        existing_app = db.query(Application).filter(Application.job_id == job.id).first()
        if not existing_app:
            new_app = Application(
                job_id=job.id,
                status="submitted",
                fields_filled=[],
                resume_used=resume_path,
                submitted_at=datetime.datetime.utcnow()
            )
            db.add(new_app)
            db.commit()
            
        stats["skipped"] += 1
        return False

    # Sanity check: verify the page title matches the job title/company to prevent applying to the wrong job
    try:
        page_title = await page.title()
        if page_title and "linkedin" in page_title.lower():
            if not ("login" in page_title.lower() or "checkpoint" in page_title.lower() or "sign in" in page_title.lower()):
                page_title_lower = page_title.lower()
                expected_company = job.company.lower()
                expected_title = job.title.lower()
                
                common_suffixes = {"inc", "incorporated", "llc", "ltd", "limited", "co", "corporation", "corp", "gmbh", "sa", "s.a.", "s.a"}
                company_words = [w.strip() for w in expected_company.replace(",", " ").replace(".", " ").split() if w.strip() and w.strip() not in common_suffixes]
                if company_words and all(len(w) < 3 for w in company_words):
                    pass
                else:
                    company_words = [w for w in company_words if len(w) >= 3]
                    
                title_words = [w.strip() for w in expected_title.replace(",", " ").replace(".", " ").replace("(", " ").replace(")", " ").replace("-", " ").replace("/", " ").split() if w.strip()]
                title_words = [w for w in title_words if len(w) >= 3]
                
                company_match = any(word in page_title_lower for word in company_words) if company_words else (expected_company in page_title_lower)
                title_match = any(word in page_title_lower for word in title_words) if title_words else (expected_title in page_title_lower)
                
                if not company_match and not title_match:
                     actual_title, actual_company = parse_job_details_from_title(page_title)
                     if actual_title and actual_company:
                         actual_url = page.url
                         actual_job_id = extract_job_id_from_url(actual_url)
                         
                         if actual_job_id:
                             actual_url = f"https://www.linkedin.com/jobs/view/{actual_job_id}"
                             
                         # Check for duplicates in database
                         existing_job = None
                         if actual_job_id:
                             existing_job = db.query(Job).filter(Job.linkedin_id == actual_job_id).first()
                             
                         if existing_job:
                             log_event(
                                 session_id, "warning", "apply",
                                 f"Page title mismatch! Expected job '{job.title}' @ '{job.company}' but page URL redirected to '{actual_title}' @ '{actual_company}' (ID: {actual_job_id}). "
                                 f"This redirected job already exists in your database. Skipping application to prevent mismatch/duplicates.",
                                 company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                             )
                             job.status = "skipped"
                             job.skip_reason = f"Redirected to existing job: {actual_title} @ {actual_company}"
                             db.commit()
                             stats["skipped"] += 1
                             return False
                         else:
                             log_event(
                                 session_id, "warning", "apply",
                                 f"Page title mismatch! Expected job '{job.title}' @ '{job.company}' but page URL redirected to '{actual_title}' @ '{actual_company}'. "
                                 f"Automatically correcting database record to match the actual job and returning it to the 'discovered' queue for review.",
                                 company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                             )
                             job.title = actual_title
                             job.company = actual_company
                             if actual_job_id:
                                 job.linkedin_id = actual_job_id
                                 job.url = actual_url
                             job.status = "discovered"
                             job.skip_reason = None
                             db.commit()
                             stats["skipped"] += 1
                             return False
                     else:
                         log_event(
                             session_id, "warning", "apply",
                             f"Page title mismatch! Expected job '{job.title}' @ '{job.company}' but page title is '{page_title}'. Skipping application to prevent mismatch.",
                             company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                         )
                         job.status = "skipped"
                         job.skip_reason = f"Page title mismatch: {page_title}"
                         db.commit()
                         stats["skipped"] += 1
                         return False
    except Exception as check_err:
        log_event(
            session_id, "warning", "apply",
            f"Error running page title match sanity check: {str(check_err)}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )

    # Check if Connect with Hiring Team is enabled
    try:
        connect_setting = db.query(Setting).filter(Setting.key == "connect_hiring_team").first()
        if connect_setting and connect_setting.value == "true":
            log_event(session_id, "info", "apply", f"Checking for hiring team members to connect...", company=job.company, job_id=job.id)
            hiring_team_links = page.locator("section:has-text('Meet the hiring team') a[href*='/in/'], section:has-text('hiring team') a[href*='/in/'], div.jobs-premium-company-growth__hiring-team a[href*='/in/']")
            count = await hiring_team_links.count()
            if count > 0:
                connected_urls = []
                for i in range(count):
                    profile_url = await hiring_team_links.nth(i).get_attribute("href")
                    if not profile_url:
                        continue
                    if profile_url.startswith("/"):
                        profile_url = f"https://www.linkedin.com{profile_url}"
                    if profile_url in connected_urls:
                        continue
                        
                    log_event(session_id, "info", "apply", f"Found hiring team profile: {profile_url}. Attempting to connect...", company=job.company, job_id=job.id)
                    new_page = await page.context.new_page()
                    try:
                        await new_page.goto(profile_url)
                        await new_page.wait_for_timeout(random.randint(2000, 4000))
                        
                        connect_btn = new_page.locator("button:has-text('Connect'), button[aria-label='Connect']").first
                        if not await connect_btn.is_visible():
                            # Try under "More" menu
                            more_btn = new_page.locator("button:has-text('More'), button[aria-label='More']").first
                            if await more_btn.is_visible():
                                await more_btn.click()
                                await new_page.wait_for_timeout(1000)
                                connect_btn = new_page.locator("div.artdeco-dropdown__content button:has-text('Connect')").first
                        
                        if await connect_btn.is_visible():
                            await connect_btn.click()
                            await new_page.wait_for_timeout(random.randint(1500, 3000))
                            
                            # Look for send without a note
                            send_btn = new_page.locator("button:has-text('Send without a note'), button:has-text('Send')").first
                            if await send_btn.is_visible():
                                await send_btn.click()
                                await new_page.wait_for_timeout(random.randint(2000, 3000))
                                
                                # Check for weekly limit error
                                error_alert = new_page.locator("text=/Your invitation to .* was not sent because you have reached the weekly limit/i")
                                if await error_alert.is_visible():
                                    log_event(session_id, "warning", "bot", "Weekly connection limit reached. Disabling 'Connect with Hiring Team' setting.")
                                    connect_setting.value = "false"
                                    db.commit()
                                    await new_page.close()
                                    break
                                else:
                                    connected_urls.append(profile_url)
                                    log_event(session_id, "success", "apply", f"Successfully sent connection request to {profile_url}", company=job.company, job_id=job.id)
                            else:
                                log_event(session_id, "info", "apply", f"Send button not found on connection modal for {profile_url}", company=job.company, job_id=job.id)
                        else:
                            log_event(session_id, "info", "apply", f"Connect button not found or already connected for {profile_url}", company=job.company, job_id=job.id)
                    except Exception as conn_err:
                        log_event(session_id, "warning", "apply", f"Failed to connect to {profile_url}: {str(conn_err)}", company=job.company, job_id=job.id)
                    finally:
                        if not new_page.is_closed():
                            await new_page.close()
                
                if connected_urls:
                    job.connected_profiles = connected_urls
                    db.commit()
                    
    except Exception as team_err:
        log_event(session_id, "warning", "apply", f"Error processing hiring team: {str(team_err)}", company=job.company, job_id=job.id)

    # Define a robust list of selectors for the Easy Apply button
    easy_apply_selectors = [
        "button.jobs-apply-button",
        "button.jobs-apply-button--top-card",
        "button[class*='jobs-apply-button']",
        "button[class*='jobs-s-apply__button']",
        "button[aria-label*='Easy Apply']",
        "button[aria-label*='Candidatura simplificada']",
        "button[aria-label*='Candidatar-se facilmente']",
        "a[aria-label*='Easy Apply']",
        "a[aria-label*='Candidatura simplificada']",
        "a[aria-label*='Candidatar-se facilmente']",
        "a[href*='openSDUIApplyFlow=true']",
        "button:has-text('Easy Apply')",
        "button:has-text('Candidatura simplificada')",
        "button:has-text('Candidatar-se facilmente')",
        "button:has-text('Candidatar-se')",
        "a:has-text('Easy Apply')",
        "a:has-text('Candidatura simplificada')",
        "a:has-text('Candidatar-se facilmente')"
    ]
    easy_apply_selector = ", ".join(easy_apply_selectors)
    
    # We will attempt to click the Easy Apply button and open the modal, retrying once if the modal doesn't open.
    modal_opened = False
    for attempt in range(1, 3):
        # First check if already applied (e.g. if page reloaded or just loaded and status is applied)
        if await check_if_already_applied(page):
            log_event(
                session_id, "info", "apply",
                f"Job already applied on LinkedIn. Skipping — {job.title} @ {job.company}",
                company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
            )
            job.status = "applied"
            db.commit()
            
            # Ensure Application entry exists
            existing_app = db.query(Application).filter(Application.job_id == job.id).first()
            if not existing_app:
                new_app = Application(
                    job_id=job.id,
                    status="submitted",
                    fields_filled=[],
                    resume_used=resume_path,
                    submitted_at=datetime.datetime.utcnow()
                )
                db.add(new_app)
                db.commit()
                
            stats["skipped"] += 1
            return False

        # Wait dynamically for the Easy Apply button to become visible (up to 8 seconds)
        easy_apply_btn = page.locator(easy_apply_selector).first
        try:
            await easy_apply_btn.wait_for(state="visible", timeout=8000)
        except Exception:
            pass
        
        if await easy_apply_btn.count() == 0:
            if attempt == 1:
                log_event(
                    session_id, "warning", "apply",
                    "Easy Apply button not found. Reloading page and retrying...",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                try:
                    await page.reload()
                    await page.wait_for_timeout(random.randint(2500, 4000))
                except Exception as re_err:
                    log_event(
                        session_id, "warning", "apply",
                        f"Failed to reload page: {str(re_err)}",
                        company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                    )
                continue
            else:
                # Capture screenshot for troubleshooting
                try:
                    screenshot_dir = os.path.join(DATA_DIR, "logs", "screenshots")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    screenshot_path = os.path.join(screenshot_dir, f"not_found_{job.id}.png")
                    await page.screenshot(path=screenshot_path)
                    log_event(
                        session_id, "info", "apply",
                        f"Saved screenshot for debugging to {screenshot_path}",
                        company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                    )
                except Exception as se:
                    log_event(
                        session_id, "warning", "apply",
                        f"Failed to capture troubleshooting screenshot: {str(se)}",
                        company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                    )

                log_event(
                    session_id, "warning", "apply",
                    "Easy Apply button not found. Job failed or unavailable.",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                job.status = "failed"
                job.skip_reason = "Easy Apply button not found"
                job.priority = 0
                db.commit()
                stats["failed"] += 1
                return False
                
        # Check LinkedIn Limit before clicking
        if await check_linkedin_limit(page):
            raise LinkedInLimitReachedException()

        # Click Easy Apply
        await easy_apply_btn.click()
        await page.wait_for_timeout(random.randint(1500, 2500))

        # Check LinkedIn Limit after clicking
        if await check_linkedin_limit(page):
            raise LinkedInLimitReachedException()
        
        # Handle LinkedIn 'Job search safety reminder' popup if it appears
        try:
            continue_btn = page.locator("button:has-text('Continue applying'), button:has-text('Continuar candidatura'), button:has-text('Continuar a candidatura'), button:has-text('Continuar aplicando'), button:has-text('Continuar a candidatar-se')").first
            review_btn = page.locator("button:has-text('Review job post'), button:has-text('Revisar vaga'), button:has-text('Rever vaga')").first
            
            if await continue_btn.count() > 0 and await continue_btn.is_visible():
                log_event(
                    session_id, "info", "apply",
                    "Job search safety reminder detected. Clicking 'Continue applying' to proceed.",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                await continue_btn.click()
                await page.wait_for_timeout(random.randint(1500, 2500))
            elif await review_btn.count() > 0 and await review_btn.is_visible():
                log_event(
                    session_id, "info", "apply",
                    "Job search safety reminder detected. Finding primary button to continue.",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                # Instead of clicking review job post, click the primary button in the dialog which is "Continue"
                primary_btn = page.locator("div[role='dialog'] button.artdeco-button--primary").first
                if await primary_btn.count() > 0 and await primary_btn.is_visible():
                    await primary_btn.click()
                    await page.wait_for_timeout(random.randint(1500, 2500))
                else:
                    # Fallback to any button that contains 'Continuar'
                    fallback_btn = page.locator("button.artdeco-button--primary:has-text('Continuar')").first
                    if await fallback_btn.count() > 0 and await fallback_btn.is_visible():
                        await fallback_btn.click()
                        await page.wait_for_timeout(random.randint(1500, 2500))
        except Exception as e:
            log_event(
                session_id, "warning", "apply",
                f"Error checking or dismissing safety reminder popup: {str(e)}",
                company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
            )
        
        # Wait dynamically for the modal dialog to appear (up to 6 seconds)
        modal_selector = "div.jobs-easy-apply-content, div[role='dialog']"
        modal = page.locator(modal_selector).first
        try:
            await modal.wait_for(state="visible", timeout=6000)
        except Exception:
            pass
            
        if await modal.count() > 0:
            modal_opened = True
            break
        else:
            if attempt == 1:
                log_event(
                    session_id, "warning", "apply",
                    "Application modal did not open after clicking Easy Apply. Reloading page and retrying...",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                try:
                    await page.reload()
                    await page.wait_for_timeout(random.randint(2500, 4000))
                except Exception as re_err:
                    log_event(
                        session_id, "warning", "apply",
                        f"Failed to reload page: {str(re_err)}",
                        company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                    )
            else:
                log_event(
                    session_id, "error", "apply",
                    "Application modal did not open after clicking Easy Apply.",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                job.status = "failed"
                job.priority = 0
                db.commit()
                stats["failed"] += 1
                return False
        
    # Fill form sequentially page-by-page
    fields_recorded = []
    
    # Delay limits configured in Settings
    min_delay = int(bot_settings.get("min_action_delay_ms", 800))
    max_delay = int(bot_settings.get("max_action_delay_ms", 3000))
    fuzzy_thresh = float(bot_settings.get("fuzzy_match_threshold", 1.0))
    
    # Resume PDF path from Profile
    profile = db.query(Profile).filter(Profile.id == 1).first()
    resume_path = profile.resume_path if profile else None
    
    try:
        steps_safety = 0
        while steps_safety < 15: # Loop protection
            # Check if modal is closed prematurely
            
            steps_safety += 1
            
            # Check LinkedIn Limit
            if await check_linkedin_limit(page):
                raise LinkedInLimitReachedException()
            
            # Check pause status
            await pause_event.wait()
            if status == "stopped":
                raise StopBotException("Execution interrupted by user.")
                
            if page.is_closed():
                raise BrowserClosedException("Browser was closed.")
                
            # Parse inputs in active step
            fields = await parse_form(page)
            
            for field in fields:
                # Check user overrides
                user_override_val = None
                if hasattr(page, "_user_overrides") and field.label in page._user_overrides:
                    user_override_val = page._user_overrides[field.label]
                    
                # If this is a FILE field override to edit on linkedin, clear it so we prompt the user
                force_manual_file = False
                if field.field_type == FieldType.FILE:
                    if user_override_val == "__edit_on_linkedin__":
                        user_override_val = None
                        force_manual_file = True
                    elif user_override_val is not None:
                        if not os.path.exists(user_override_val):
                            user_override_val = None
                    
                if user_override_val is not None:
                    log_event(session_id, "info", "apply", f"Applying user override for '{field.label}': '{user_override_val}'")
                    await fill_field(page, field, user_override_val)
                    fields_recorded.append({
                        "label": field.label,
                        "value": str(user_override_val),
                        "source": "user_edit",
                        "field_type": field.field_type.value,
                        "options": field.options
                    })
                # Handle File inputs (Resume, Cover Letters, etc.)
                elif field.field_type == FieldType.FILE:
                    # Check if a file is already pre-selected on LinkedIn
                    is_preselected = False
                    if field.current_value is not None and not force_manual_file:
                        is_preselected = True
                        
                    # If there's an error message, we must NOT treat it as preselected/valid
                    if field.error_message:
                        is_preselected = False
                        
                    if is_preselected:
                        log_event(session_id, "info", "apply", f"File field '{field.label}' already has pre-selected file: '{field.current_value}'. Skipping upload/popup.")
                        fields_recorded.append({
                            "label": field.label,
                            "value": field.current_value,
                            "source": "preselected",
                            "field_type": field.field_type.value,
                            "options": []
                        })
                        continue

                    label_lower = field.label.lower()
                    # Determine if it's a resume or cover letter / general upload
                    is_resume = any(kw in label_lower for kw in ["resume", "cv", "currículo", "curriculo", "curriculum", "resumé"])
                    
                    file_to_upload = None
                    
                    if is_resume:
                        if resume_path and os.path.exists(resume_path) and not field.error_message and not force_manual_file:
                            file_to_upload = resume_path
                        else:
                            # Prompt the user to upload a resume
                            log_event(session_id, "warning", "apply", f"Resume PDF not configured or has error: {field.error_message}. Requesting upload.")
                            payload = {
                                "type": "question_file",
                                "title": "Configure Resume" if not field.error_message else "Resume Upload Error",
                                "question": field.label,
                                "message": "No active resume PDF was found in your profile. Please upload a resume." if not field.error_message else f"The previous upload failed: {field.error_message}",
                                "file_hint": field.file_hint or "PDF (512 KB)",
                                "company": job.company,
                                "job_title": job.title,
                                "job_url": job.url,
                                "options": field.options
                            }
                            if field.error_message:
                                payload["error_message"] = field.error_message
                            file_to_upload, _ = await show_popup(payload)
                            # If they uploaded a new resume, update the profile path
                            if file_to_upload and os.path.exists(file_to_upload):
                                profile = db.query(Profile).filter(Profile.id == 1).first()
                                if profile:
                                    profile.resume_path = file_to_upload
                                    db.commit()
                                    db.refresh(profile)
                                    resume_path = file_to_upload
                    else:
                        # Cover letter or other file upload!
                        log_event(session_id, "info", "apply", f"File field '{field.label}' encountered. Requesting file upload.")
                        payload = {
                            "type": "question_file",
                            "title": "Upload File",
                            "question": field.label,
                            "message": f"Please upload the requested file: '{field.label}'",
                            "file_hint": field.file_hint or "DOC, DOCX, PDF (512 KB)",
                            "company": job.company,
                            "job_title": job.title,
                            "job_url": job.url,
                            "options": field.options
                        }
                        if field.error_message:
                            payload["error_message"] = field.error_message
                        file_to_upload, _ = await show_popup(payload)
                        
                    if file_to_upload == "__stop_bot__":
                        raise StopBotException("Execution interrupted by user via popup.")
                    elif file_to_upload == "__close_popup__":
                        raise ClosePopupException("User closed the popup.")
                    elif file_to_upload == "__skip_job__":
                        raise SkipJobException("User chose to skip this job.")
                    elif file_to_upload == "__skip_question__":
                        log_event(session_id, "info", "apply", f"Skipping file field '{field.label}' by user request.")
                        fields_recorded.append({
                            "label": field.label,
                            "value": "",
                            "source": "skipped",
                            "field_type": field.field_type.value,
                            "options": []
                        })
                    else:
                        if file_to_upload.startswith("__use_linkedin_file__:"):
                            selected_name = file_to_upload.split("__use_linkedin_file__:", 1)[1]
                            log_event(session_id, "info", "apply", f"Selecting existing file '{selected_name}' on LinkedIn.")
                            
                            clicked = False
                            selectors = [
                                f"div:has-text('{selected_name}')",
                                f"label:has-text('{selected_name}')",
                                f"span:has-text('{selected_name}')",
                                f"p:has-text('{selected_name}')"
                            ]
                            for sel in selectors:
                                loc = page.locator(sel)
                                c = await loc.count()
                                for i in range(c):
                                    item = loc.nth(i)
                                    if await item.is_visible():
                                        # Try to find the closest card container or radio element
                                        card = item.locator("xpath=ancestor-or-self::*[contains(@class, 'jobs-resume-card') or contains(@class, 'jobs-document-card') or @role='radio' or @type='radio' or contains(@class, 'checkbox')]").first
                                        if await card.count() > 0:
                                            await card.click()
                                        else:
                                            await item.click()
                                        clicked = True
                                        break
                                if clicked:
                                    break
                                    
                            if not clicked:
                                try:
                                    await page.get_by_text(selected_name).first.click()
                                    clicked = True
                                except Exception:
                                    pass
                                    
                            fields_recorded.append({
                                "label": field.label,
                                "value": selected_name,
                                "source": "user_edit" if force_manual_file else "preselected",
                                "field_type": field.field_type.value,
                                "options": []
                            })
                        else:
                            if not file_to_upload or not os.path.exists(file_to_upload):
                                raise SkipJobException("No file provided by the user.")
                                
                            await fill_field(page, field, file_to_upload)
                            fields_recorded.append({
                                "label": field.label,
                                "value": os.path.basename(file_to_upload),
                                "source": "user_upload" if not is_resume else "profile",
                                "field_type": field.field_type.value,
                                "options": []
                            })
                else:
                    # Check if the field is already pre-filled on LinkedIn
                    is_prefilled = False
                    if field.current_value is not None:
                        if not is_placeholder_value(field.current_value):
                            is_prefilled = True
                            
                    # If the field has a validation error, we must NOT skip it as prefilled!
                    if field.error_message:
                        is_prefilled = False
                    
                    if is_prefilled:
                        # If already pre-filled, save it to the Q&A Bank as user info and don't re-fill
                        log_event(
                            session_id, "info", "apply", 
                            f"Field '{field.label}' is already pre-filled with '{field.current_value}'. Skipping fill."
                        )
                        # Save to Q&A Bank!
                        try:
                            from backend.bot.qa_resolver import normalize
                            from backend.models import QAEntry
                            norm_q = normalize(field.label)
                            existing_qa = db.query(QAEntry).filter(QAEntry.normalized_question == norm_q).first()
                            if existing_qa:
                                # Update if it was empty or auto-generated
                                if existing_qa.answer != str(field.current_value):
                                    existing_qa.answer = str(field.current_value)
                                    existing_qa.field_type = field.field_type.value
                                    existing_qa.source = "user"
                                    db.commit()
                            else:
                                new_qa = QAEntry(
                                    question=field.label,
                                    normalized_question=norm_q,
                                    answer=str(field.current_value),
                                    field_type=field.field_type.value,
                                    source="user"
                                )
                                db.add(new_qa)
                                db.commit()
                                log_event(session_id, "success", "qa", f"Pre-filled answer saved to Q&A Bank: '{field.label}' -> '{field.current_value}'")
                        except Exception as e:
                            log_event(session_id, "warning", "qa", f"Failed to auto-save pre-filled value: {str(e)}")
                        
                        fields_recorded.append({
                            "label": field.label,
                            "value": str(field.current_value),
                            "source": "prefilled",
                            "field_type": field.field_type.value,
                            "options": field.options
                        })
                    else:
                        # Standard fields
                        resolved_val, source = await resolve_field_value(field, job, session_id, db, fuzzy_thresh)
                        if resolved_val == "__skip_question__":
                            log_event(session_id, "info", "apply", f"Skipping standard field '{field.label}' by user request.")
                            fields_recorded.append({
                                "label": field.label,
                                "value": str(field.current_value) if field.current_value is not None else "",
                                "source": "skipped",
                                "field_type": field.field_type.value,
                                "options": field.options
                            })
                        else:
                            await fill_field(page, field, resolved_val)
                            fields_recorded.append({
                                "label": field.label,
                                "value": str(resolved_val),
                                "source": source,
                                "field_type": field.field_type.value,
                                "options": field.options
                            })
                    
                await human_delay(min_delay, max_delay)
                
            # Check for next buttons
            next_btn_selectors = [
                "button[aria-label*='next step']",
                "button[aria-label*='Avançar']",
                "button[aria-label*='Siguiente']",
                "button:has-text('Next')",
                "button:has-text('Avançar')",
                "button:has-text('Siguiente')",
                "button:has-text('Continuar')",
                "button:has-text('Review')",
                "button:has-text('Revisar')"
            ]

            submit_btn_selectors = [
                "button[aria-label*='Submit application']",
                "button[aria-label*='Enviar candidatura']",
                "button[aria-label*='Enviar solicitud']",
                "button:has-text('Submit application')",
                "button:has-text('Submit')",
                "button:has-text('Enviar candidatura')",
                "button:has-text('Enviar solicitude')",
                "button:has-text('Enviar')"
            ]

            # Scope next and submit buttons to the Easy Apply modal if open to prevent matching background elements (like pagination buttons)
            modal_container = page.locator("div.jobs-easy-apply-content, div[role='dialog'], [data-test-modal-id='easy-apply-modal']").first
            if await modal_container.count() > 0:
                next_btn = modal_container.locator(", ".join(next_btn_selectors)).first
                submit_btn = modal_container.locator(", ".join(submit_btn_selectors)).first
            else:
                next_btn = page.locator(", ".join(next_btn_selectors)).first
                submit_btn = page.locator(", ".join(submit_btn_selectors)).first
            
            if await next_btn.count() > 0:
                # Clicking next step
                await next_btn.click()
                await page.wait_for_timeout(random.randint(1500, 2500))
                # Check LinkedIn Limit after clicking
                if await check_linkedin_limit(page):
                    raise LinkedInLimitReachedException()
            elif await submit_btn.count() > 0:
                # We reached final submission step
                
                # Check submission mode setting
                submission_mode = bot_settings.get("bot_mode", "review")
                
                if submission_mode == "review":
                    # Display blocking Review confirmation popup
                    log_event(
                        session_id, "action", "apply",
                        f"Review required for {job.title} @ {job.company} (displaying popup)",
                        company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                    )
                    
                    review_payload = {
                        "type": "review_submit",
                        "title": f"Review — {job.title} @ {job.company}",
                        "message": f"Do you want to submit the application for {job.company}?",
                        "confirm_label": "Submit Application",
                        "cancel_label": "Cancel & Skip",
                        "company": job.company,
                        "job_title": job.title,
                        "job_url": job.url,
                        "fields": fields_recorded
                    }
                    
                    approved, _ = await show_popup(review_payload)
                    if approved == "__stop_bot__":
                        raise StopBotException("Execution interrupted by user via popup.")
                    if approved == "__close_popup__":
                        raise ClosePopupException("User closed the popup.")
                    if not approved or approved == "__skip_job__":
                        raise SkipJobException("Application cancelled by the user during the review step.")
                        
                    if isinstance(approved, dict) and "fields" in approved:
                        edited_fields = approved["fields"]
                        edited_map = {f["label"]: f["value"] for f in edited_fields}
                        
                        has_changes = False
                        for recorded in fields_recorded:
                            label = recorded["label"]
                            if label in edited_map and str(edited_map[label]) != str(recorded["value"]):
                                has_changes = True
                                log_event(session_id, "info", "apply", f"User modified '{label}' to '{edited_map[label]}'")
                                
                                # Update Q&A Bank
                                try:
                                    from backend.bot.qa_resolver import normalize
                                    from backend.models import QAEntry
                                    norm_q = normalize(label)
                                    existing_qa = db.query(QAEntry).filter(QAEntry.normalized_question == norm_q).first()
                                    if existing_qa:
                                        existing_qa.answer = str(edited_map[label])
                                        existing_qa.source = "user"
                                        db.commit()
                                    else:
                                        new_qa = QAEntry(
                                            question=label,
                                            normalized_question=norm_q,
                                            answer=str(edited_map[label]),
                                            field_type=recorded.get("field_type", "text"),
                                            source="user"
                                        )
                                        db.add(new_qa)
                                        db.commit()
                                except Exception as qa_err:
                                    log_event(session_id, "warning", "qa", f"Failed to save manual edit: {str(qa_err)}")
                        
                        if has_changes:
                            log_event(session_id, "info", "apply", "Going back to apply user edits...")
                            back_btn_selectors = [
                                "button[data-easy-apply-back-button]",
                                "button[aria-label*='back' i]",
                                "button[aria-label*='voltar' i]",
                                "button[aria-label*='regresar' i]",
                                "button[class*='back' i]",
                                "button:has-text('Back')",
                                "button:has-text('Voltar')",
                                "button:has-text('Regresar')",
                                "button:has-text('Atrás')"
                            ]
                            
                            back_count = 0
                            while back_count < 15:
                                try:
                                    # Scope back button to the Easy Apply modal container if open
                                    modal_container = page.locator("div.jobs-easy-apply-content, div[role='dialog'], [data-test-modal-id='easy-apply-modal']").first
                                    if await modal_container.count() > 0:
                                        back_btn = modal_container.locator(", ".join(back_btn_selectors)).first
                                    else:
                                        back_btn = page.locator(", ".join(back_btn_selectors)).first
                                    if await back_btn.count() > 0 and await back_btn.is_visible() and await back_btn.is_enabled():
                                        await back_btn.click()
                                        await page.wait_for_timeout(random.randint(1500, 2000))
                                        back_count += 1
                                    else:
                                        break
                                except Exception as click_err:
                                    log_event(session_id, "warning", "apply", f"Retrying back button click due to: {str(click_err)}")
                                    await page.wait_for_timeout(1000)
                            
                            if not hasattr(page, "_user_overrides"):
                                page._user_overrides = {}
                            page._user_overrides.update(edited_map)
                            
                            steps_safety = 0
                            fields_recorded.clear()
                            continue
                        
                # Submit
                delay_submit = int(bot_settings.get("auto_submit_delay_ms", 2000))
                await asyncio.sleep(delay_submit / 1000.0)
                await submit_btn.click()
                await page.wait_for_timeout(random.randint(2000, 3500))
                
                # Close post-application dialog screen
                close_btn = page.locator("button[aria-label='Dismiss'], button.artdeco-modal__dismiss").first
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await page.wait_for_timeout(1000)
                    
                # Save to database
                job.status = "applied"
                job.priority = 0
                db.commit()
                
                new_app = Application(
                    job_id=job.id,
                    status="submitted",
                    fields_filled=fields_recorded,
                    resume_used=resume_path,
                    submitted_at=datetime.datetime.utcnow()
                )
                db.add(new_app)
                db.commit()
                
                log_event(
                    session_id, "success", "apply",
                    f"Application submitted successfully! — {job.title} @ {job.company}",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                stats["applied"] += 1
                
                try:
                    await process_hiring_team_followup(page, job, session_id, db, bot_settings)
                except Exception as follow_err:
                    log_event(session_id, "warning", "apply", f"Hiring team follow-up encountered an error: {str(follow_err)}", company=job.company, job_id=job.id)
                    
                return True

            else:
                # No buttons found, stuck
                raise Exception("No action button ('Next' or 'Submit') was found on the screen.")
                
    except LinkedInLimitReachedException as e:
        log_event(
            session_id, "warning", "apply",
            f"LinkedIn Easy Apply daily limit reached. Saving job as queued and prioritizing. — {job.title} @ {job.company}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        job.status = "queued"
        job.priority = 10
        db.commit()
        try:
            await close_easy_apply_dialog(page)
        except Exception:
            pass
        raise e
    except ClosePopupException as e:
        log_event(
            session_id, "info", "apply",
            f"Popup closed. Job skipped and added to end of queue — {job.title} @ {job.company}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        job.status = "queued"
        job.priority = 0
        job.discovered_at = datetime.datetime.utcnow()
        db.commit()
        stats["skipped"] += 1
        await close_easy_apply_dialog(page)
        return False
    except (StopBotException, BrowserClosedException) as e:
        log_event(
            session_id, "info", "apply",
            f"Application interrupted (stopped/browser closed). Saving job as queued and prioritizing. — {job.title} @ {job.company}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        job.status = "queued"
        job.priority = 10
        db.commit()
        try:
            await close_easy_apply_dialog(page)
        except Exception:
            pass
        raise e
    except SkipJobException as e:
        log_event(
            session_id, "info", "apply",
            f"Job skipped: {str(e)}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        job.status = "skipped"
        job.skip_reason = str(e)
        job.priority = 0
        db.commit()
        stats["skipped"] += 1
        await close_easy_apply_dialog(page)
        return False
    except Exception as e:
        exc_name = type(e).__name__
        if exc_name == "ClosePopupException":
            log_event(
                session_id, "info", "apply",
                f"Popup closed. Job skipped and added to end of queue — {job.title} @ {job.company}",
                company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
            )
            job.status = "queued"
            job.priority = 0
            job.discovered_at = datetime.datetime.utcnow()
            db.commit()
            stats["skipped"] += 1
            await close_easy_apply_dialog(page)
            return False
        elif exc_name == "LinkedInLimitReachedException" or isinstance(e, LinkedInLimitReachedException):
            log_event(
                session_id, "warning", "apply",
                f"LinkedIn Easy Apply daily limit reached. Saving job as queued and prioritizing. — {job.title} @ {job.company}",
                company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
            )
            job.status = "queued"
            job.priority = 10
            db.commit()
            try:
                await close_easy_apply_dialog(page)
            except Exception:
                pass
            raise e
        elif exc_name in ("StopBotException", "BrowserClosedException") or isinstance(e, (StopBotException, BrowserClosedException)) or is_browser_closed_exception(e):
            log_event(
                session_id, "info", "apply",
                f"Application interrupted (stopped/browser closed). Saving job as queued and prioritizing. — {job.title} @ {job.company}",
                company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
            )
            job.status = "queued"
            job.priority = 10
            db.commit()
            try:
                await close_easy_apply_dialog(page)
            except Exception:
                pass
            raise e
        elif exc_name == "SkipJobException":
            log_event(
                session_id, "info", "apply",
                f"Job skipped: {str(e)}",
                company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
            )
            job.status = "skipped"
            job.skip_reason = str(e)
            job.priority = 0
            db.commit()
            stats["skipped"] += 1
            await close_easy_apply_dialog(page)
            return False
            
        log_event(
            session_id, "error", "apply",
            f"Error during application: {str(e)}",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
        job.status = "failed"
        job.priority = 0
        db.commit()
        stats["failed"] += 1
        await close_easy_apply_dialog(page)
        return False

async def close_easy_apply_dialog(page: Page):
    """
    Closes the Easy Apply modal if open, discarding the draft state.
    """
    try:
        close_btn = page.locator("button[aria-label='Dismiss'], button.artdeco-modal__dismiss").first
        if await close_btn.count() > 0:
            await close_btn.click()
            await page.wait_for_timeout(800)
            
            # Check for "Discard application?" prompt
            discard_btn = page.locator("button[data-control-name='discard_application_confirm_btn'], button:has-text('Discard'), button:has-text('Descartar')").first
            if await discard_btn.count() > 0:
                await discard_btn.click()
                await page.wait_for_timeout(800)
    except Exception:
        pass

async def process_queue(page: Page, db: Session, bot_settings: Dict[str, Any], target: str = "all", initial_run: bool = False):
    """
    Process and apply to jobs currently in the queue, either all or just prioritized.
    """
    global session_id, status
    
    # Check pause status
    await pause_event.wait()
    if status in ["stopped", "finished"]:
        return
        
    if target == "prioritized":
        queued_jobs = db.query(Job).filter(Job.status == "queued", Job.priority > 0).order_by(Job.priority.desc(), Job.discovered_at.asc()).all()
    else:
        queued_jobs = db.query(Job).filter(Job.status == "queued").order_by(Job.priority.desc(), Job.discovered_at.asc()).all()

    if queued_jobs:
        run_desc = "pre-existing queued" if initial_run else "newly discovered"
        log_event(
            session_id, "info", "bot",
            f"Processing {len(queued_jobs)} {run_desc} jobs in queue. Starting applications..."
        )
        for job in queued_jobs:
            # Check pause status
            await pause_event.wait()
            if status in ["stopped", "finished"]:
                break
                
            # Applying state
            await update_status("applying")
            try:
                global current_job_task
                current_job_task = asyncio.create_task(apply_to_job(page, job, session_id, db, bot_settings))
                await current_job_task
            except asyncio.CancelledError:
                # Task was cancelled to immediately skip the job
                log_event(
                    session_id, "info", "apply",
                    "Job skipped manually from dashboard.",
                    company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                )
                stats["skipped"] += 1
                await close_easy_apply_dialog(page)
            except LinkedInLimitReachedException:
                raise
            finally:
                current_job_task = None
            await broadcast_status()
            
            # Prevent rapid operations spam (Anti-detection)
            await human_delay(1500, 3500)

async def bot_loop(tasks: Optional[List[Any]], launch_mode: str):
    """
    Core bot execution runner coordinates state changes and session flows.
    """
    global session_id, stats, browser_session
    session_id = str(uuid.uuid4())
    stats = {"found": 0, "applied": 0, "skipped": 0, "failed": 0, "popups": 0}
    
    # Clear any stale popup from a previous session
    from backend.bot import popup_manager
    popup_manager.active_popup = None
    popup_manager.popup_response_value = None
    popup_manager.popup_response_event.clear()
    
    db = SessionLocal()
    try:
        # Determine search_id for session (just use the first search task's id if any)
        session_search_id = None
        if tasks:
            for t in tasks:
                t_dict = t.model_dump() if hasattr(t, "model_dump") else t
                if t_dict.get("type") == "search" and t_dict.get("search_id"):
                    session_search_id = t_dict["search_id"]
                    break

        # Create execution session record in SQLite
        sess_record = SessionModel(
            id=session_id,
            status="running",
            mode=launch_mode,
            started_at=datetime.datetime.utcnow(),
            search_id=session_search_id
        )
        db.add(sess_record)
        db.commit()
        
        # Load active configurations
        settings = db.query(Setting).all()
        bot_settings = {s.key: s.value for s in settings}
        
        # Check if we can proceed
        if not tasks:
            log_event(session_id, "error", "system", "No valid tasks specified.")
            await update_status("stopped")
            return
            
        start_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_event(
            session_id, "info", "bot",
            f"Session started on {start_time_str} (Mode: {launch_mode}) · ID: {session_id[:8]}"
        )
        await update_status("running")
        
        # Launch browser context
        browser_session = BrowserSession()
        # Force headless=False so Chrome always opens a visible window
        headless = False
        page = await browser_session.start(headless=headless)
        
        global active_page
        active_page = page
        
        # Check authentication state
        await update_status("checking_auth")
        log_event(session_id, "info", "auth", "Checking LinkedIn authentication status...")
        
        authenticated = await check_auth(page, session_id)
        if not authenticated:
            log_event(session_id, "warning", "auth", "User is logged out. Requesting manual login in Chrome...")
            await update_status("waiting_login")
            
            # Show blocking popup requesting manual login
            ans, _ = await show_popup({
                "type": "manual_action",
                "title": "🔑 Log in to LinkedIn",
                "message": "The Chrome window opened to LinkedIn. Please log in to your account normally. If you use two-factor authentication, complete it as well. The bot will automatically resume once it detects you are logged in.",
                "action_label": "Done / Continue"
            })
            if ans == "__stop_bot__":
                raise StopBotException("Execution interrupted by user via popup.")
            
            # Polling to wait for login
            login_safety = 0
            while login_safety < 120: # 4 mins timeout
                await asyncio.sleep(2)
                if await check_auth(page, session_id, force_navigate=False):
                    log_event(session_id, "success", "auth", "Login detected successfully!")
                    break
                login_safety += 1
            else:
                log_event(session_id, "error", "auth", "Login timeout exceeded. Stopping bot.")
                await update_status("stopped")
                return
                

        limit_reached = False

        # Process each task in order
        for task in tasks:
            if limit_reached:
                break
                
            task_dict = task.model_dump() if hasattr(task, "model_dump") else task
            task_type = task_dict.get("type")
            
            # Check pause status
            await pause_event.wait()
            # Check if bot was stopped
            if status in ["stopped", "finished"]:
                break
                
            if task_type == "process_queue":
                target = task_dict.get("target", "all")
                try:
                    await process_queue(page, db, bot_settings, target=target, initial_run=False)
                except LinkedInLimitReachedException:
                    limit_reached = True
                    log_event(session_id, "warning", "bot", f"Daily LinkedIn Easy Apply limit reached during queue processing. Stopping session.")
                    db_setting = db.query(Setting).filter(Setting.key == "easy_apply_limit_reached").first()
                    if not db_setting:
                        db_setting = Setting(key="easy_apply_limit_reached", value="true")
                        db.add(db_setting)
                    else:
                        db_setting.value = "true"
                        db_setting.updated_at = datetime.datetime.utcnow()
                    db.commit()

            elif task_type == "search":
                search_id = task_dict.get("search_id")
                if not search_id:
                    continue
                    
                criteria = db.query(SearchCriteria).filter(SearchCriteria.id == search_id).first()
                if not criteria:
                    log_event(session_id, "warning", "bot", f"Search criteria {search_id} not found. Skipping task.")
                    continue
                    
                log_event(session_id, "info", "bot", f"Starting search: '{criteria.name}'")
                await update_status("searching")
                session_limit = criteria.max_per_session if criteria.max_per_session and criteria.max_per_session > 0 else int(bot_settings.get("session_limit", 10))
                discovered = await discover_jobs(page, criteria, session_id, db, session_limit, pause_event=pause_event)
                
                stats["found"] += len(discovered)
                await broadcast_status()
                
                await update_status("queued")
                
                for job in discovered:
                    await pause_event.wait()
                    if status in ["stopped", "finished"]:
                        break
                        
                    if launch_mode == "review":
                        await update_status("review_pending")
                        log_event(
                            session_id, "action", "bot",
                            f"Awaiting approval for job {job.title} @ {job.company}",
                            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
                        )
                        
                        job_approved, _ = await show_popup({
                            "type": "confirm",
                            "title": "Approve Application?",
                            "message": f"Do you want to apply to '{job.title}' at '{job.company}'?",
                            "confirm_label": "Approve",
                            "cancel_label": "Skip",
                            "company": job.company,
                            "job_title": job.title,
                            "job_url": job.url
                        })
                        if job_approved == "__stop_bot__":
                            raise StopBotException("Execution interrupted by user via popup.")
                        
                        if job_approved == "__close_popup__":
                            job.status = "queued"
                            job.priority = 0
                            job.discovered_at = datetime.datetime.utcnow()
                            db.commit()
                            log_event(session_id, "info", "apply", f"Job popup closed. Added to end of queue: {job.title} @ {job.company}")
                            await broadcast_status()
                            continue
                        
                        if not job_approved:
                            job.status = "skipped"
                            job.skip_reason = "Rejected by user in queue"
                            job.priority = 0
                            db.commit()
                            stats["skipped"] += 1
                            log_event(session_id, "info", "apply", f"Job skipped by user: {job.title} @ {job.company}")
                            await broadcast_status()
                            continue
                        
                        job.status = "queued"
                        job.priority = 0
                        db.commit()
                        log_event(session_id, "success", "apply", f"Job approved and added to queue: {job.title} @ {job.company}")
                        await broadcast_status()
                    else:
                        job.status = "queued"
                        job.priority = 0
                        db.commit()
                        log_event(session_id, "success", "apply", f"Job automatically added to queue: {job.title} @ {job.company}")
                        await broadcast_status()

        log_event(session_id, "success", "bot", "End of job application session.")
        if limit_reached:
            await update_status("stopped")
        else:
            await update_status("finished")
        
    except StopBotException:
        log_event(session_id, "info", "bot", "Bot execution stopped by user via popup.")
        await update_status("stopped")
    except LinkedInLimitReachedException:
        log_event(session_id, "warning", "bot", "Daily LinkedIn Easy Apply limit reached. Stopping session.")
        db_setting = db.query(Setting).filter(Setting.key == "easy_apply_limit_reached").first()
        if not db_setting:
            db_setting = Setting(key="easy_apply_limit_reached", value="true")
            db.add(db_setting)
        else:
            db_setting.value = "true"
            db_setting.updated_at = datetime.datetime.utcnow()
        db.commit()
        await update_status("stopped")
    except asyncio.CancelledError:
        log_event(session_id, "info", "bot", "Bot execution cancelled/stopped by user.")
        await update_status("stopped")
        raise
    except Exception as e:
        if type(e).__name__ == "StopBotException" or isinstance(e, StopBotException):
            log_event(session_id, "info", "bot", "Bot execution stopped by user via popup.")
            await update_status("stopped")
        else:
            log_event(session_id, "error", "system", f"Fatal error in session: {str(e)}")
            await update_status("stopped")
    finally:
        db.close()
        if browser_session:
            await browser_session.close()
            browser_session = None

def start_bot(tasks: Optional[List[Any]], launch_mode: str) -> str:
    """
    Spawns the bot loop as a background task.
    """
    global bot_task, mode
    mode = launch_mode
    pause_event.set() # Unpause if it was paused
    
    # Reset daily limit reached setting
    db = SessionLocal()
    try:
        setting = db.query(Setting).filter(Setting.key == "easy_apply_limit_reached").first()
        if setting:
            setting.value = "false"
            db.commit()
    except Exception as e:
        pass
    finally:
        db.close()
        
    bot_task = asyncio.create_task(bot_loop(tasks, launch_mode))
    return "Session started."

def pause_bot():
    global status, previous_status
    if status not in ["idle", "stopped", "finished", "paused"]:
        previous_status = status
        pause_event.clear()
        status = "paused"
        if session_id:
            db = SessionLocal()
            try:
                sess = db.query(SessionModel).filter(SessionModel.id == session_id).first()
                if sess:
                    sess.status = "paused"
                    db.commit()
            finally:
                db.close()
        # Broadcast
        asyncio.create_task(broadcast_status())
        return "Session paused."
    return "Bot is not running."

def resume_bot():
    global status
    if status == "paused":
        pause_event.set()
        status = previous_status
        if session_id:
            db = SessionLocal()
            try:
                sess = db.query(SessionModel).filter(SessionModel.id == session_id).first()
                if sess:
                    sess.status = previous_status
                    db.commit()
            finally:
                db.close()
        asyncio.create_task(broadcast_status())
        return "Session resumed."
    return "Bot is not paused."

def stop_bot():
    global status, bot_task
    if status != "idle":
        status = "stopped"
        pause_event.set() # Release wait bounds
        if bot_task:
            bot_task.cancel()
            bot_task = None
        try:
            from backend.bot.popup_manager import close_active_popups
            close_active_popups()
        except Exception:
            pass
        asyncio.create_task(update_status("stopped"))
        return "Session stopped."
    return "Bot is already idle."


async def process_hiring_team_followup(page: Page, job: Job, session_id: str, db: Session, bot_settings: dict):
    # 1. Scrape hiring team link(s)
    # Check if connect_hiring_team is enabled.
    connect_setting = db.query(Setting).filter(Setting.key == "connect_hiring_team").first()
    if not connect_setting or connect_setting.value != "true":
        return

    log_event(session_id, "info", "apply", "Looking for hiring team recruiter details...", company=job.company, job_id=job.id)
    
    # Locate elements in the hiring team section
    hiring_team_section = page.locator("section:has-text('Meet the hiring team'), section:has-text('hiring team'), div.jobs-premium-company-growth__hiring-team")
    if await hiring_team_section.count() == 0:
        log_event(session_id, "info", "apply", "No hiring team section found on the job details page.", company=job.company, job_id=job.id)
        return

    # Find the link to their profile
    profile_links = hiring_team_section.locator("a[href*='/in/']")
    link_count = await profile_links.count()
    if link_count == 0:
        log_event(session_id, "info", "apply", "No recruiter profiles found in the hiring team section.", company=job.company, job_id=job.id)
        return

    # Scrape recruiter links
    recruiter_urls = []
    for i in range(link_count):
        href = await profile_links.nth(i).get_attribute("href")
        if href:
            if href.startswith("/"):
                href = f"https://www.linkedin.com{href}"
            # Clean up the url
            href = href.split("?")[0].rstrip("/")
            if href not in recruiter_urls:
                recruiter_urls.append(href)

    log_event(session_id, "info", "apply", f"Found {len(recruiter_urls)} potential recruiter profile(s).", company=job.company, job_id=job.id)

    connected_urls = list(job.connected_profiles or [])

    # Process each recruiter sequentially
    for recruiter_url in recruiter_urls:
        new_page = None
        try:
            log_event(session_id, "info", "apply", f"Processing recruiter profile: {recruiter_url}", company=job.company, job_id=job.id)
            
            # Open profile in a new tab
            new_page = await page.context.new_page()
            await new_page.goto(recruiter_url)
            await new_page.wait_for_timeout(random.randint(3000, 5000))
            
            # Scrape name
            name_el = new_page.locator("h1.text-heading-xlarge, h1.pv-text-details__left-panel-title, .pv-top-card-layout__title, h1[class*='inline-t-']").first
            recruiter_name = "Recruiter"
            if await name_el.is_visible():
                raw_name = await name_el.inner_text()
                if raw_name:
                    recruiter_name = raw_name.strip()
            
            # Scrape connection degree
            connection_status = "unknown"
            top_card_text = ""
            top_card_el = new_page.locator(".pv-text-details__left-panel, .pv-top-card-layout").first
            if await top_card_el.is_visible():
                top_card_text = await top_card_el.inner_text()
            
            if "1st" in top_card_text or "1º" in top_card_text:
                connection_status = "1st"
            elif "2nd" in top_card_text or "2º" in top_card_text:
                connection_status = "2nd"
            elif "3rd" in top_card_text or "3º" in top_card_text:
                connection_status = "3rd"
            
            # Scrape Contact Info
            email = None
            phone = None
            websites = []
            
            # Go to contact overlay
            contact_url = f"{recruiter_url}/overlay/contact-info/"
            await new_page.goto(contact_url)
            await new_page.wait_for_timeout(random.randint(2000, 4000))
            
            # Scrape details from contact info overlay
            email_el = new_page.locator("a[href^='mailto:']").first
            if await email_el.is_visible():
                email_href = await email_el.get_attribute("href")
                if email_href:
                    email = email_href.replace("mailto:", "").strip()
            
            # Scrape phone
            phone_el = new_page.locator("section.ci-phone span, .ci-phone li").first
            if await phone_el.is_visible():
                phone = (await phone_el.inner_text()).strip()
            
            # Scrape websites
            website_elements = new_page.locator("section.ci-websites a")
            web_count = await website_elements.count()
            for w_idx in range(web_count):
                web_href = await website_elements.nth(w_idx).get_attribute("href")
                if web_href:
                    websites.append(web_href.strip())

            log_event(session_id, "info", "apply", f"Scraped details for {recruiter_name}: Degree: {connection_status}, Email: {email}, Phone: {phone}", company=job.company, job_id=job.id)

            # Check if this contact already exists in database, or create it
            contact_db = db.query(RecruiterContact).filter(RecruiterContact.linkedin_url == recruiter_url).first()
            if not contact_db:
                contact_db = RecruiterContact(
                    job_id=job.id,
                    name=recruiter_name,
                    linkedin_url=recruiter_url,
                    email=email,
                    phone=phone,
                    websites=websites,
                    connection_status=connection_status,
                    company=job.company
                )
                db.add(contact_db)
            else:
                contact_db.job_id = job.id
                contact_db.name = recruiter_name
                contact_db.email = email or contact_db.email
                contact_db.phone = phone or contact_db.phone
                contact_db.websites = websites or contact_db.websites
                contact_db.connection_status = connection_status
                contact_db.company = job.company
            db.commit()

            # Now return to profile page
            await new_page.goto(recruiter_url)
            await new_page.wait_for_timeout(2000)

            # Determine language based on job details
            language = "en"
            if job.location and any(p in job.location.lower() for p in ["brazil", "brasil", "portugal", "angola", "moçambique"]):
                language = "pt"
            elif job.description and any(w in job.description.lower() for w in ["requisitos", "benefícios", "experiência", "vaga", "contratação"]):
                language = "pt"

            profile_db = db.query(Profile).filter(Profile.id == 1).first()
            candidate_name = f"{profile_db.first_name or ''} {profile_db.last_name or ''}".strip() or "Candidate"
            resume_link = profile_db.resume_hosted_url or ""

            # Extract recruiter's first name, cleaning common titles
            recruiter_first_name = recruiter_name.strip()
            if recruiter_first_name:
                for title in ["mr.", "ms.", "mrs.", "dr.", "prof.", "eng."]:
                    if recruiter_first_name.lower().startswith(title):
                        recruiter_first_name = recruiter_first_name[len(title):].strip()
                        break
                recruiter_first_name = recruiter_first_name.split()[0]
            if not recruiter_first_name:
                recruiter_first_name = "Recruiter"

            # ---------------- LINKEDIN MESSAGE STEP ----------------
            weekly_limit_reached = False
            is_non_connected = (connection_status != "1st")
            if is_non_connected:
                seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
                sent_count = db.query(ContactLog).filter(
                    ContactLog.type == "linkedin_message",
                    ContactLog.is_non_connected == True,
                    ContactLog.sent_at >= seven_days_ago
                ).count()
                if sent_count >= 10:
                    weekly_limit_reached = True
                    log_event(session_id, "warning", "apply", f"Weekly message limit to non-connections reached ({sent_count}/10). Skipping LinkedIn message to {recruiter_name}.", company=job.company, job_id=job.id)

            if not weekly_limit_reached:
                # Find all active templates of type linkedin_message for the detected language
                active_templates = db.query(MessageTemplate).filter(
                    MessageTemplate.language == language,
                    MessageTemplate.type == "linkedin_message",
                    MessageTemplate.is_active == True
                ).all()
                
                selected_template = None
                if active_templates:
                    selected_template = random.choice(active_templates)
                    template_body = selected_template.body
                else:
                    template_body = (
                        "Olá, {recruiter_first_name}. Acabei de me candidatar à vaga de {job} na {company} e gostaria de reforçar meu interesse. Possuo experiência relevante e gostaria de me conectar. Abraço!"
                        if language == "pt" else
                        "Hi {recruiter_first_name}, I just applied for the {job} position at {company} and wanted to express my enthusiasm. I'd love to connect and share how my background fits the role. Best!"
                    )
                
                # Format variables safely
                format_dict = {
                    "recruiter_name": recruiter_name,
                    "recruiter_first_name": recruiter_first_name,
                    "job": job.title,
                    "company": job.company,
                    "candidate_name": candidate_name,
                    "resume_link": resume_link
                }
                
                def safe_format(text, data):
                    for k, v in data.items():
                        text = text.replace("{" + k + "}", str(v))
                    return text

                rendered_msg = safe_format(template_body, format_dict)

                popup_payload = {
                    "popup_id": str(uuid.uuid4()),
                    "type": "confirm_message",
                    "title": f"Send LinkedIn Message to {recruiter_name}",
                    "company": job.company,
                    "job_title": job.title,
                    "recruiter_name": recruiter_name,
                    "recruiter_url": recruiter_url,
                    "connection_status": connection_status,
                    "current_value": rendered_msg,
                    "save": True
                }

                user_msg, should_send = await show_popup(popup_payload)

                if should_send and user_msg != "__skip_job__" and user_msg != "__close_popup__":
                    log_event(session_id, "info", "apply", f"Sending LinkedIn message to {recruiter_name}...", company=job.company, job_id=job.id)
                    
                    msg_sent = False
                    message_btn = new_page.locator("button:has-text('Message'), button[aria-label^='Message']").first
                    if await message_btn.is_visible():
                        await message_btn.click()
                        await new_page.wait_for_timeout(2000)
                        
                        textbox = new_page.locator("div[role='textbox'], div[contenteditable='true'], textarea").first
                        if await textbox.is_visible():
                            await textbox.focus()
                            await type_human(textbox, user_msg)
                            await new_page.wait_for_timeout(1000)
                            
                            send_btn = new_page.locator("button[type='submit'], button:has-text('Send')").first
                            if await send_btn.is_visible():
                                await send_btn.click()
                                await new_page.wait_for_timeout(2000)
                                msg_sent = True
                                log_event(session_id, "success", "apply", f"Successfully sent LinkedIn message to {recruiter_name}!", company=job.company, job_id=job.id)
                                
                                new_log = ContactLog(
                                    recruiter_id=contact_db.id,
                                    job_id=job.id,
                                    template_id=selected_template.id if selected_template else None,
                                    type="linkedin_message",
                                    status="sent",
                                    body=user_msg,
                                    is_non_connected=is_non_connected
                                )
                                db.add(new_log)
                                db.commit()
                                connected_urls.append(recruiter_url)
                            else:
                                log_event(session_id, "warning", "apply", "Send button not found in messaging overlay.", company=job.company, job_id=job.id)
                        else:
                            log_event(session_id, "warning", "apply", "Text entry box not found in LinkedIn messaging overlay.", company=job.company, job_id=job.id)
                    else:
                        log_event(session_id, "info", "apply", f"Direct message button not available. Sending connection request with note to {recruiter_name}.", company=job.company, job_id=job.id)
                        connect_btn = new_page.locator("button:has-text('Connect'), button[aria-label^='Connect']").first
                        if not await connect_btn.is_visible():
                            more_btn = new_page.locator("button:has-text('More'), button[aria-label^='More']").first
                            if await more_btn.is_visible():
                                await more_btn.click()
                                await new_page.wait_for_timeout(1000)
                                connect_btn = new_page.locator("div.artdeco-dropdown__content button:has-text('Connect')").first
                        
                        if await connect_btn.is_visible():
                            await connect_btn.click()
                            await new_page.wait_for_timeout(1500)
                            
                            add_note_btn = new_page.locator("button:has-text('Add a note')").first
                            if await add_note_btn.is_visible():
                                await add_note_btn.click()
                                await new_page.wait_for_timeout(1000)
                                
                                note_box = new_page.locator("textarea[name='message']").first
                                if await note_box.is_visible():
                                    short_msg = user_msg[:295]
                                    await note_box.focus()
                                    await type_human(note_box, short_msg)
                                    await new_page.wait_for_timeout(1000)
                                    
                                    send_btn = new_page.locator("button:has-text('Send'), button:has-text('Send invitation')").first
                                    if await send_btn.is_visible():
                                        await send_btn.click()
                                        await new_page.wait_for_timeout(2000)
                                        msg_sent = True
                                        log_event(session_id, "success", "apply", f"Successfully sent connection request with note to {recruiter_name}!", company=job.company, job_id=job.id)
                                        
                                        new_log = ContactLog(
                                            recruiter_id=contact_db.id,
                                            job_id=job.id,
                                            template_id=selected_template.id if selected_template else None,
                                            type="linkedin_message",
                                            status="sent",
                                            body=short_msg,
                                            is_non_connected=is_non_connected
                                        )
                                        db.add(new_log)
                                        db.commit()
                                        connected_urls.append(recruiter_url)
                        
                    if not msg_sent:
                        log_event(session_id, "warning", "apply", f"Could not message or connect with {recruiter_name} on LinkedIn (Premium lock or selector issue).", company=job.company, job_id=job.id)
                        new_log = ContactLog(
                            recruiter_id=contact_db.id,
                            job_id=job.id,
                            template_id=selected_template.id if selected_template else None,
                            type="linkedin_message",
                            status="failed",
                            body=user_msg,
                            is_non_connected=is_non_connected
                        )
                        db.add(new_log)
                        db.commit()

            # ---------------- GMAIL STEP ----------------
            if email:
                # Find active templates of type email for the language
                active_templates_email = db.query(MessageTemplate).filter(
                    MessageTemplate.language == language,
                    MessageTemplate.type == "email",
                    MessageTemplate.is_active == True
                ).all()

                selected_template_email = None
                if active_templates_email:
                    selected_template_email = random.choice(active_templates_email)
                    email_sub = selected_template_email.subject
                    email_body = selected_template_email.body
                else:
                    email_sub = "Candidatura: {job} - {candidate_name}" if language == "pt" else "Application: {job} - {candidate_name}"
                    email_body = (
                        "Prezado(a) {recruiter_name},\n\nEspero que este e-mail o(a) encontre bem.\n\nEscrevo para expressar meu interesse na vaga de {job} na {company}, para a qual acabei de me candidatar através do LinkedIn.\n\nFico à disposição para conversar e compartilhar mais detalhes.\n\nAtenciosamente,\n{candidate_name}"
                        if language == "pt" else
                        "Dear {recruiter_name},\n\nI hope this email finds you well.\n\nI am writing to express my strong interest in the {job} position at {company}, which I recently applied for via LinkedIn.\n\nI look forward to the possibility of discussing this opportunity further.\n\nBest regards,\n{candidate_name}"
                    )

                format_dict = {
                    "recruiter_name": recruiter_name,
                    "recruiter_first_name": recruiter_first_name,
                    "job": job.title,
                    "company": job.company,
                    "candidate_name": candidate_name,
                    "resume_link": resume_link
                }

                rendered_sub = safe_format(email_sub or "Application", format_dict)
                rendered_body_email = safe_format(email_body, format_dict)

                popup_payload_email = {
                    "popup_id": str(uuid.uuid4()),
                    "type": "confirm_email",
                    "title": f"Send Follow-up Email to {recruiter_name}",
                    "company": job.company,
                    "job_title": job.title,
                    "recruiter_name": recruiter_name,
                    "email": email,
                    "subject": rendered_sub,
                    "current_value": rendered_body_email,
                    "save": True
                }

                edited_body, should_send_email = await show_popup(popup_payload_email)

                user_email_sub = rendered_sub
                user_email_body = edited_body

                if isinstance(edited_body, dict):
                    user_email_sub = edited_body.get("subject", rendered_sub)
                    user_email_body = edited_body.get("body", "")

                if should_send_email and edited_body != "__skip_job__" and edited_body != "__close_popup__":
                    log_event(session_id, "info", "apply", f"Automating Gmail compose flow to {email}...", company=job.company, job_id=job.id)
                    
                    gmail_page = await new_page.context.new_page()
                    try:
                        await gmail_page.goto("https://mail.google.com/")
                        await gmail_page.wait_for_timeout(3000)
                        
                        if "signin" in gmail_page.url or await gmail_page.locator("input[type='email'], a:has-text('Sign in')").first.is_visible():
                            log_event(session_id, "warning", "apply", "Gmail is not logged in. Pausing for user login...", company=job.company, job_id=job.id)
                            login_payload = {
                                "popup_id": str(uuid.uuid4()),
                                "type": "manual_action",
                                "title": "Log in to Gmail",
                                "message": "Please log in to your Google Account in the opened Chrome browser window. Once you are logged in and see your inbox, click 'Continue' here.",
                                "save": False
                            }
                            await show_popup(login_payload)
                            await gmail_page.wait_for_timeout(3000)
                        
                        await gmail_page.goto("https://mail.google.com/mail/u/0/#inbox?compose=new")
                        await gmail_page.wait_for_timeout(4000)
                        
                        to_selector = "input[aria-label*='To'], input[aria-label*='Para'], input[placeholder*='Recipients'], textarea[aria-label*='To']"
                        subject_selector = "input[name='subjectbox'], input[placeholder='Subject'], input[placeholder='Assunto']"
                        body_selector = "div[role='textbox'][aria-label*='Message Body'], div[role='textbox'][aria-label*='Corpo da mensagem'], div[role='textbox']"
                        
                        to_field = gmail_page.locator(to_selector).first
                        await to_field.wait_for(state="visible", timeout=15000)
                        await to_field.focus()
                        await type_human(to_field, email)
                        await gmail_page.keyboard.press("Enter")
                        await gmail_page.wait_for_timeout(1000)
                        
                        sub_field = gmail_page.locator(subject_selector).first
                        await sub_field.focus()
                        await type_human(sub_field, user_email_sub)
                        await gmail_page.wait_for_timeout(1000)
                        
                        body_field = gmail_page.locator(body_selector).first
                        await body_field.focus()
                        await type_human(body_field, user_email_body)
                        await gmail_page.wait_for_timeout(1500)
                        
                        send_selector = "div[role='button']:has-text('Send'), div[role='button']:has-text('Enviar'), div[aria-label*='Send'], div[aria-label*='Enviar']"
                        send_btn = gmail_page.locator(send_selector).first
                        await send_btn.click()
                        await gmail_page.wait_for_timeout(3000)
                        
                        log_event(session_id, "success", "apply", f"Successfully sent follow-up email to {email}!", company=job.company, job_id=job.id)
                        
                        new_log = ContactLog(
                            recruiter_id=contact_db.id,
                            job_id=job.id,
                            template_id=selected_template_email.id if selected_template_email else None,
                            type="email",
                            status="sent",
                            subject=user_email_sub,
                            body=user_email_body,
                            is_non_connected=False
                        )
                        db.add(new_log)
                        db.commit()
                        
                    except Exception as gmail_err:
                        log_event(session_id, "error", "apply", f"Failed to automate email sending: {str(gmail_err)}", company=job.company, job_id=job.id)
                        new_log = ContactLog(
                            recruiter_id=contact_db.id,
                            job_id=job.id,
                            template_id=selected_template_email.id if selected_template_email else None,
                            type="email",
                            status="failed",
                            subject=user_email_sub,
                            body=user_email_body,
                            is_non_connected=False
                        )
                        db.add(new_log)
                        db.commit()
                    finally:
                        if not gmail_page.is_closed():
                            await gmail_page.close()


            # Close recruiter profile page tab
            if not new_page.is_closed():
                await new_page.close()

        except Exception as recruiter_err:
            log_event(session_id, "warning", "apply", f"Error processing recruiter {recruiter_url}: {str(recruiter_err)}", company=job.company, job_id=job.id)
        finally:
            if new_page and not new_page.is_closed():
                await new_page.close()

    if connected_urls:
        job.connected_profiles = connected_urls
        db.commit()

