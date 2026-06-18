import csv
import io
import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.database import get_db
from backend.models import QAEntry
from backend.schemas import QAEntryResponse, QAEntryCreate, QAEntryUpdate
from backend.services.fuzzy_matcher import normalize

router = APIRouter(prefix="/api/qa", tags=["Q&A Bank"])

@router.get("", response_model=List[QAEntryResponse])
def list_qa(
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(QAEntry)
    if q:
        query = query.filter(
            (QAEntry.question.ilike(f"%{q}%")) | 
            (QAEntry.answer.ilike(f"%{q}%")) |
            (QAEntry.notes.ilike(f"%{q}%"))
        )
    
    offset = (page - 1) * limit
    return query.order_by(QAEntry.created_at.desc()).offset(offset).limit(limit).all()

@router.post("", response_model=QAEntryResponse)
def create_qa(payload: QAEntryCreate, db: Session = Depends(get_db)):
    norm_q = normalize(payload.question)
    
    # Check if duplicate normalized question exists
    existing = db.query(QAEntry).filter(QAEntry.normalized_question == norm_q).first()
    if existing:
        raise HTTPException(status_code=400, detail="A similar question already exists in the Q&A bank.")
        
    qa = QAEntry(
        question=payload.question,
        normalized_question=norm_q,
        answer=payload.answer,
        field_type=payload.field_type,
        options_hash=payload.options_hash,
        source="user",
        notes=payload.notes
    )
    db.add(qa)
    db.commit()
    db.refresh(qa)
    return qa

@router.put("/{qa_id}", response_model=QAEntryResponse)
def update_qa(qa_id: int, payload: QAEntryUpdate, db: Session = Depends(get_db)):
    qa = db.query(QAEntry).filter(QAEntry.id == qa_id).first()
    if not qa:
        raise HTTPException(status_code=404, detail="Q&A entry not found.")
        
    data = payload.model_dump(exclude_unset=True)
    if "question" in data and data["question"] != qa.question:
        qa.normalized_question = normalize(data["question"])
        
    for key, value in data.items():
        setattr(qa, key, value)
        
    qa.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(qa)
    return qa

@router.delete("/{qa_id}")
def delete_qa(qa_id: int, db: Session = Depends(get_db)):
    qa = db.query(QAEntry).filter(QAEntry.id == qa_id).first()
    if not qa:
        raise HTTPException(status_code=404, detail="Q&A entry not found.")
    db.delete(qa)
    db.commit()
    return {"message": "Q&A entry deleted successfully."}

@router.get("/export")
def export_qa(db: Session = Depends(get_db)):
    qas = db.query(QAEntry).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["question", "answer", "field_type", "notes"])
    
    for qa in qas:
        writer.writerow([qa.question, qa.answer, qa.field_type or "text", qa.notes or ""])
        
    output.seek(0)
    
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=qa_bank.csv"
    return response

@router.post("/import")
async def import_qa(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    
    contents = await file.read()
    try:
        decoded = contents.decode("utf-8")
    except UnicodeDecodeError:
        decoded = contents.decode("latin-1")
        
    reader = csv.DictReader(io.StringIO(decoded))
    imported_count = 0
    
    for row in reader:
        # Check standard headers
        question = row.get("question") or row.get("Question")
        answer = row.get("answer") or row.get("Answer")
        if not question or not answer:
            continue
            
        field_type = row.get("field_type") or row.get("Field Type") or "text"
        notes = row.get("notes") or row.get("Notes") or ""
        
        norm_q = normalize(question)
        
        # Merge if normalized question already exists, otherwise insert new
        existing = db.query(QAEntry).filter(QAEntry.normalized_question == norm_q).first()
        if existing:
            existing.answer = answer
            existing.field_type = field_type
            existing.notes = notes
            existing.source = "imported"
            existing.updated_at = datetime.datetime.utcnow()
        else:
            new_qa = QAEntry(
                question=question,
                normalized_question=norm_q,
                answer=answer,
                field_type=field_type,
                source="imported",
                notes=notes
            )
            db.add(new_qa)
        imported_count += 1
        
    db.commit()
    return {"message": f"Successfully imported {imported_count} Q&A entries."}
