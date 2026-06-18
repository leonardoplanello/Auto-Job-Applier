import re
from typing import Optional, Tuple, Any
from sqlalchemy.orm import Session
from backend.models import Profile, QAEntry, Job
from backend.bot.form_parser import FormField, FieldType
from backend.services.fuzzy_matcher import exact_match, fuzzy_match, normalize
from backend.bot.popup_manager import show_popup
from backend.services.logger import log_event

# Special Exception to skip the current job midway
class SkipJobException(Exception):
    pass

class BrowserClosedException(Exception):
    pass

class StopBotException(Exception):
    pass

class ClosePopupException(Exception):
    pass

def is_browser_closed_exception(e: Exception) -> bool:
    msg = str(e).lower()
    return (
        "target page, context or browser has been closed" in msg
        or "browser closed" in msg
        or "context closed" in msg
        or "connection closed" in msg
        or "page.evaluate: closed" in msg
        or "target closed" in msg
    )


# Layer 1 Regex Mapping to Profile columns
PROFILE_FIELD_MAP = {
    # Names
    r"\bfirst\s*name\b": lambda p: p.first_name,
    r"\blast\s*name|surname\b": lambda p: p.last_name,
    r"\bfull\s*name\b": lambda p: f"{p.first_name or ''} {p.last_name or ''}".strip(),

    # Contact Info
    r"\bphone|mobile|telephone|celular|telefone\b": lambda p: p.phone,
    r"\bemail\b": lambda p: p.email,

    # Location Info
    r"\bcity|cidade|ciudad\b": lambda p: p.city,
    r"\bstate|province|estado|provincia\b": lambda p: p.state,
    r"\bcountry|país|pais\b": lambda p: p.country,
    r"\bzip|postal|cep|zipcode\b": lambda p: p.zip_code,

    # Professional URLs
    r"\blinkedin\s*(url|profile)\b": lambda p: p.linkedin_url,
    r"\bgithub\b": lambda p: p.github_url,
    r"\bportfolio|website|site\b": lambda p: p.portfolio_url,

    # Personal Documents
    r"\bcpf\b": lambda p: p.cpf,

    # Current Job
    r"\bcurrent\s*(company|employer)\b": lambda p: p.current_company,
    r"\bcurrent\s*(title|position|role)\b": lambda p: p.current_title,
}

def resolve_from_profile(label: str, profile: Profile) -> Optional[str]:
    """
    Tries to match form input label against regular expressions for standard profile columns.
    """
    clean_lbl = label.lower()
    for pattern, extractor in PROFILE_FIELD_MAP.items():
        if re.search(pattern, clean_lbl):
            val = extractor(profile)
            if val:
                return str(val)
    return None

async def resolve_field_value(
    field: FormField,
    job: Job,
    session_id: str,
    db: Session,
    fuzzy_threshold: float = 1.0
) -> Tuple[Any, str]:
    """
    Resolves a form field value by traversing through:
    Profile Map -> Exact Q&A Match -> Fuzzy Q&A Match -> Popup Modal.
    Returns:
        (resolved_value, source_name)
    """
    # Fetch active profile
    profile = db.query(Profile).filter(Profile.id == 1).first()
    
    # Layer 1-3 are bypassed if the field has a validation error to let the user correct it
    if not field.error_message:
        # Layer 1: Profile Mapping
        if profile:
            profile_val = resolve_from_profile(field.label, profile)
            if profile_val:
                # For SELECT/RADIO, check if the value matches one of the options (case insensitive)
                if field.field_type in [FieldType.SELECT, FieldType.RADIO]:
                    if not field.options:
                        return profile_val, "profile"
                    for opt in field.options:
                        if opt.lower().strip() == profile_val.lower().strip():
                            return opt, "profile"
                    # If it didn't match directly, fall through to other layers
                else:
                    return profile_val, "profile"

        # Layer 2: Exact Match in Q&A SQLite Bank
        exact_qa = exact_match(db, field.label)
        if exact_qa:
            # Check option bounds for selectable fields
            if field.field_type in [FieldType.SELECT, FieldType.RADIO]:
                if not field.options:
                    exact_qa.times_used += 1
                    db.commit()
                    return exact_qa.answer, "qa_bank"
                for opt in field.options:
                    if opt.lower().strip() == exact_qa.answer.lower().strip():
                        # Update usage stats
                        exact_qa.times_used += 1
                        db.commit()
                        return opt, "qa_bank"
            else:
                exact_qa.times_used += 1
                db.commit()
                return exact_qa.answer, "qa_bank"

        # Layer 3: Fuzzy Match in Q&A SQLite Bank
        fuzzy_qa = fuzzy_match(db, field.label, threshold=fuzzy_threshold)
        if fuzzy_qa:
            # Check option bounds for selectable fields
            if field.field_type in [FieldType.SELECT, FieldType.RADIO]:
                if not field.options:
                    fuzzy_qa.times_used += 1
                    db.commit()
                    return fuzzy_qa.answer, "qa_bank"
                for opt in field.options:
                    if opt.lower().strip() == fuzzy_qa.answer.lower().strip():
                        # Update usage stats
                        fuzzy_qa.times_used += 1
                        db.commit()
                        return opt, "qa_bank"
            else:
                fuzzy_qa.times_used += 1
                db.commit()
                return fuzzy_qa.answer, "qa_bank"

    # Layer 4: Popup Modal
    if field.error_message:
        log_event(
            session_id, "action", "qa",
            f"Validation error at {job.company} for '{field.label}': {field.error_message} (displaying popup)",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
    else:
        log_event(
            session_id, "action", "qa",
            f"Unknown question at {job.company}: '{field.label}' (displaying popup)",
            company=job.company, job_title=job.title, job_url=job.url, job_id=job.id
        )
    
    # Determine popup configuration based on form field type
    popup_payload = {
        "company": job.company,
        "job_title": job.title,
        "job_url": job.url,
        "question": field.label,
        "options": field.options
    }
    
    if field.error_message:
        popup_payload["error_message"] = field.error_message
    if field.current_value is not None:
        popup_payload["current_value"] = field.current_value
    
    if field.field_type == FieldType.NUMBER:
        popup_payload["type"] = "question_number"
        popup_payload["title"] = "Numerical Answer"
    elif field.field_type in [FieldType.SELECT, FieldType.RADIO] and field.options:
        popup_payload["type"] = "question_select"
        popup_payload["title"] = "Choose an option"
    elif field.field_type == FieldType.CHECKBOX:
        popup_payload["type"] = "question_checkbox"
        popup_payload["title"] = "Check the option"
    else:
        popup_payload["type"] = "question_text"
        popup_payload["title"] = "New Question"
        popup_payload["field_hint"] = "free text"

    # Block and wait for WebSocket response
    answer_val, save_in_db = await show_popup(popup_payload)
    
    if answer_val == "__skip_question__":
        return "__skip_question__", "skipped"
        
    # If the user chose to skip the job
    if answer_val == "__skip_job__":
        raise SkipJobException("User chose to skip this job.")
        
    if answer_val == "__stop_bot__":
        raise StopBotException("Execution interrupted by user via popup.")
        
    if answer_val == "__close_popup__":
        raise ClosePopupException("User closed the popup.")
        
    if answer_val is None:
        raise SkipJobException("No answer provided by the user.")

    # Save to Q&A Bank if specified
    if save_in_db:
        norm_q = normalize(field.label)
        # Verify it wasn't added by another request in the meantime
        existing_qa = db.query(QAEntry).filter(QAEntry.normalized_question == norm_q).first()
        if existing_qa:
            existing_qa.answer = str(answer_val)
            existing_qa.field_type = field.field_type.value
            existing_qa.source = "user"
        else:
            new_qa = QAEntry(
                question=field.label,
                normalized_question=norm_q,
                answer=str(answer_val),
                field_type=field.field_type.value,
                source="user"
            )
            db.add(new_qa)
        db.commit()
        log_event(session_id, "success", "qa", f"Answer saved in Q&A Bank: '{field.label}' -> '{answer_val}'")

    return answer_val, "user"
