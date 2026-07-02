import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import RecruiterContact, ContactLog, MessageTemplate
from backend.schemas import (
    RecruiterContactResponse, RecruiterContactUpdate, RecruiterContactBase,
    ContactLogResponse,
    MessageTemplateResponse, MessageTemplateUpdate, MessageTemplateBase,
    ConnectionStats
)

router = APIRouter(prefix="/api/connections", tags=["Connections"])

# --- Recruiters / Contacts Endpoints ---

@router.get("", response_model=List[RecruiterContactResponse])
def list_contacts(db: Session = Depends(get_db)):
    return db.query(RecruiterContact).order_by(RecruiterContact.discovered_at.desc()).all()

@router.put("/{contact_id}", response_model=RecruiterContactResponse)
def update_contact(contact_id: int, payload: RecruiterContactUpdate, db: Session = Depends(get_db)):
    contact = db.query(RecruiterContact).filter(RecruiterContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Recruiter contact not found.")
    
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, key, value)
    
    db.commit()
    db.refresh(contact)
    return contact

@router.delete("/{contact_id}")
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    contact = db.query(RecruiterContact).filter(RecruiterContact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Recruiter contact not found.")
    
    db.delete(contact)
    db.commit()
    return {"status": "success", "message": "Recruiter contact deleted."}

# --- Message / Email Templates Endpoints ---

def make_template_response(t: MessageTemplate, db: Session) -> dict:
    now = datetime.datetime.utcnow()
    one_day_ago = now - datetime.timedelta(days=1)
    one_week_ago = now - datetime.timedelta(days=7)
    one_month_ago = now - datetime.timedelta(days=30)
    
    used_day = db.query(ContactLog).filter(ContactLog.template_id == t.id, ContactLog.sent_at >= one_day_ago).count()
    used_week = db.query(ContactLog).filter(ContactLog.template_id == t.id, ContactLog.sent_at >= one_week_ago).count()
    used_month = db.query(ContactLog).filter(ContactLog.template_id == t.id, ContactLog.sent_at >= one_month_ago).count()
    used_all = db.query(ContactLog).filter(ContactLog.template_id == t.id).count()
    
    return {
        "id": t.id,
        "name": t.name,
        "language": t.language,
        "type": t.type,
        "subject": t.subject,
        "body": t.body,
        "is_active": t.is_active,
        "used_day": used_day,
        "used_week": used_week,
        "used_month": used_month,
        "used_all": used_all,
        "created_at": t.created_at,
        "updated_at": t.updated_at
    }

@router.get("/templates", response_model=List[MessageTemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(MessageTemplate).order_by(MessageTemplate.language, MessageTemplate.type).all()
    return [make_template_response(t, db) for t in templates]

@router.post("/templates", response_model=MessageTemplateResponse)
def create_template(payload: MessageTemplateBase, db: Session = Depends(get_db)):
    template = MessageTemplate(
        name=payload.name,
        language=payload.language,
        type=payload.type,
        subject=payload.subject,
        body=payload.body,
        is_active=payload.is_active
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return make_template_response(template, db)

@router.put("/templates/{template_id}", response_model=MessageTemplateResponse)
def update_template(template_id: int, payload: MessageTemplateUpdate, db: Session = Depends(get_db)):
    template = db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")
    
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    
    template.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(template)
    return make_template_response(template, db)

@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found.")
    
    db.delete(template)
    db.commit()
    return {"status": "success", "message": "Template deleted."}

# --- Connection Logs Endpoints ---

@router.get("/logs", response_model=List[ContactLogResponse])
def list_logs(db: Session = Depends(get_db)):
    return db.query(ContactLog).order_by(ContactLog.sent_at.desc()).all()

# --- Connection Statistics (Weekly limit) ---

@router.get("/stats", response_model=ConnectionStats)
def get_stats(db: Session = Depends(get_db)):
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    
    # Count how many messages were sent to non-connected recruiters in the last 7 days
    count = db.query(ContactLog).filter(
        ContactLog.type == "linkedin_message",
        ContactLog.is_non_connected == True,
        ContactLog.sent_at >= seven_days_ago
    ).count()
    
    return ConnectionStats(weekly_non_connected_sent=count)
