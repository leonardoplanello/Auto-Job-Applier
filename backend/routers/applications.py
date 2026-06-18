from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from backend.database import get_db
from backend.models import Application
from backend.schemas import ApplicationResponse, ApplicationUpdate

router = APIRouter(prefix="/api/applications", tags=["Applications"])

@router.get("", response_model=List[ApplicationResponse])
def list_applications(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(Application)
    if status:
        query = query.filter(Application.status == status)
    
    offset = (page - 1) * limit
    return query.order_by(Application.submitted_at.desc()).offset(offset).limit(limit).all()

@router.get("/export")
def export_applications(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from backend.models import Job
    
    query = db.query(Application).join(Job)
    if status:
        query = query.filter(Application.status == status)
        
    apps = query.order_by(Application.submitted_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "application_id", "job_id", "linkedin_id", "job_title", "company", "location", "job_url",
        "status", "submitted_at", "resume_used", "notes"
    ])
    
    for app in apps:
        writer.writerow([
            app.id,
            app.job_id,
            app.job.linkedin_id if app.job else "",
            app.job.title if app.job else "",
            app.job.company if app.job else "",
            app.job.location if app.job else "",
            app.job.url if app.job else "",
            app.status,
            app.submitted_at.isoformat() + "Z" if app.submitted_at else "",
            app.resume_used or "",
            app.notes or ""
        ])
        
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=applications.csv"
    return response

@router.get("/{app_id}", response_model=ApplicationResponse)
def get_application(app_id: int, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")
    return app

@router.patch("/{app_id}", response_model=ApplicationResponse)
def update_application(app_id: int, payload: ApplicationUpdate, db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")
    
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(app, key, value)
    
    app.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(app)
    return app
