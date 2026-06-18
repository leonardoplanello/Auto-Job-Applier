import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from backend.database import get_db, DATA_DIR
from backend.models import Profile
from backend.schemas import ProfileResponse, ProfileUpdate

router = APIRouter(prefix="/api/profile", tags=["Profile"])

def get_or_create_profile(db: Session) -> Profile:
    profile = db.query(Profile).filter(Profile.id == 1).first()
    if not profile:
        profile = Profile(id=1, country="Brazil")
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile

@router.get("", response_model=ProfileResponse)
def get_profile(db: Session = Depends(get_db)):
    return get_or_create_profile(db)

@router.put("", response_model=ProfileResponse)
def update_profile(profile_data: ProfileUpdate, db: Session = Depends(get_db)):
    profile = get_or_create_profile(db)
    for key, value in profile_data.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return profile

@router.post("/resume", response_model=ProfileResponse)
async def upload_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF resumes are supported.")
    
    resume_dir = os.path.join(DATA_DIR, "user_files")
    os.makedirs(resume_dir, exist_ok=True)
    
    file_path = os.path.join(resume_dir, "resume.pdf")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save resume: {str(e)}")
        
    profile = get_or_create_profile(db)
    profile.resume_path = file_path
    db.commit()
    db.refresh(profile)
    return profile

@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    # Create a directory for temp uploads / attachments
    upload_dir = os.path.join(DATA_DIR, "user_files")
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = file.filename
    # Avoid path traversal
    filename = os.path.basename(filename)
    file_path = os.path.join(upload_dir, filename)
    
    # Check if file already exists, if so, append uuid suffix
    if os.path.exists(file_path):
        import uuid
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{uuid.uuid4().hex[:6]}{ext}"
        file_path = os.path.join(upload_dir, filename)
        
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
        
    return {"filepath": file_path, "filename": filename}

