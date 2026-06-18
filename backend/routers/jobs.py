import time
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models import Job, SearchCriteria
from backend.schemas import JobResponse, JobApprove, JobSkip, BulkJobAction

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])

@router.get("", response_model=List[JobResponse])
def list_jobs(
    status: Optional[str] = None,
    company: Optional[str] = None,
    search_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=10000),
    db: Session = Depends(get_db)
):
    query = db.query(Job)
    if status and status != "all":
        query = query.filter(Job.status == status)
    if company:
        query = query.filter(Job.company.ilike(f"%{company}%"))
    if search_id:
        query = query.filter(Job.search_id == search_id)
    
    offset = (page - 1) * limit
    return query.order_by(Job.discovered_at.desc()).offset(offset).limit(limit).all()

@router.get("/export")
def export_jobs(
    status: Optional[str] = None,
    company: Optional[str] = None,
    search_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    query = db.query(Job)
    if status and status != "all":
        query = query.filter(Job.status == status)
    if company:
        query = query.filter(Job.company.ilike(f"%{company}%"))
    if search_id:
        query = query.filter(Job.search_id == search_id)
        
    jobs = query.order_by(Job.discovered_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "linkedin_id", "title", "company", "location", "remote", "easy_apply", "status", "url", "discovered_at", "skip_reason"])
    
    for job in jobs:
        writer.writerow([
            job.id,
            job.linkedin_id,
            job.title,
            job.company,
            job.location or "",
            job.remote if job.remote is not None else "",
            job.easy_apply,
            job.status,
            job.url,
            job.discovered_at.isoformat() + "Z" if job.discovered_at else "",
            job.skip_reason or ""
        ])
        
    output.seek(0)
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=jobs.csv"
    return response

# ─── Bulk Action Endpoints ────────────────────────────────────────────────────

@router.post("/bulk/skip")
def bulk_skip(payload: BulkJobAction, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided.")
    db.query(Job).filter(Job.id.in_(payload.job_ids)).update(
        {"status": "skipped", "skip_reason": "Skipped by user"},
        synchronize_session=False
    )
    db.commit()
    from backend.bot import engine
    background_tasks.add_task(engine.broadcast_status)
    return {"updated": len(payload.job_ids)}

@router.post("/bulk/approve")
def bulk_approve(payload: BulkJobAction, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided.")
    db.query(Job).filter(Job.id.in_(payload.job_ids)).update(
        {"status": "queued", "skip_reason": None, "priority": 0},
        synchronize_session=False
    )
    db.commit()
    from backend.bot import engine
    background_tasks.add_task(engine.broadcast_status)
    return {"updated": len(payload.job_ids)}

@router.post("/bulk/prioritize")
def bulk_prioritize(payload: BulkJobAction, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided.")
    
    current_time_val = int(time.time() * 1000) # milliseconds
    db.query(Job).filter(Job.id.in_(payload.job_ids)).update(
        {"status": "queued", "skip_reason": None, "priority": current_time_val},
        synchronize_session=False
    )
    db.commit()
    from backend.bot import engine
    background_tasks.add_task(engine.broadcast_status)
    return {"updated": len(payload.job_ids)}

@router.post("/bulk/reorder")
def bulk_reorder(payload: BulkJobAction, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided.")
    
    base_priority = int(time.time() * 1000)
    total = len(payload.job_ids)
    
    mappings = []
    for i, job_id in enumerate(payload.job_ids):
        # First ID gets highest priority, subsequent IDs get incrementally lower priority
        mappings.append({"id": job_id, "priority": base_priority + total - i})
        
    db.bulk_update_mappings(Job, mappings)
    db.commit()
    from backend.bot import engine
    background_tasks.add_task(engine.broadcast_status)
    return {"reordered": total}

@router.post("/bulk/delete")
def bulk_delete(payload: BulkJobAction, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided.")
    db.query(Job).filter(Job.id.in_(payload.job_ids)).delete(synchronize_session=False)
    db.commit()
    from backend.bot import engine
    background_tasks.add_task(engine.broadcast_status)
    return {"deleted": len(payload.job_ids)}

@router.post("/bulk/blacklist-company")
def bulk_blacklist_company(payload: BulkJobAction, db: Session = Depends(get_db)):
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="No job IDs provided.")
    # Collect unique company names from the selected jobs
    jobs = db.query(Job).filter(Job.id.in_(payload.job_ids)).all()
    companies_to_block = list({j.company for j in jobs if j.company})
    if not companies_to_block:
        return {"message": "No companies found for the selected jobs."}
    # Append to every SearchCriteria's blacklist_companies (deduped)
    all_criteria = db.query(SearchCriteria).all()
    for criteria in all_criteria:
        existing = list(criteria.blacklist_companies or [])
        merged = list({*existing, *companies_to_block})
        criteria.blacklist_companies = merged
    db.commit()
    return {"blacklisted": companies_to_block}

# ─── Single Job Endpoints ─────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job

@router.post("/{job_id}/approve", response_model=JobResponse)
def approve_job(job_id: int, payload: JobApprove, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    # Mode can be 'review' or 'auto'. If approved, status goes to queued
    job.status = "queued"
    job.skip_reason = None
    job.priority = 0
    db.commit()
    db.refresh(job)
    from backend.bot import engine
    background_tasks.add_task(engine.broadcast_status)
    return job

@router.post("/{job_id}/skip", response_model=JobResponse)
async def skip_job(job_id: int, payload: JobSkip, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    
    job.status = "skipped"
    job.skip_reason = payload.reason
    job.priority = 0
    db.commit()
    db.refresh(job)

    # Check if this is the currently processing job
    from backend.bot import engine, popup_manager
    if engine.current_job_id == job.id:
        if popup_manager.active_popup:
            await popup_manager.resolve_popup("__skip_job__", False)
        elif engine.current_job_task and not engine.current_job_task.done():
            engine.current_job_task.cancel()
            
    background_tasks.add_task(engine.broadcast_status)
    return job
