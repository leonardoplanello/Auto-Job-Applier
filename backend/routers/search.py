from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend.models import SearchCriteria
from backend.schemas import SearchCriteriaResponse, SearchCriteriaCreate

router = APIRouter(prefix="/api/search", tags=["Search Criteria"])

@router.get("", response_model=List[SearchCriteriaResponse])
def list_search_criteria(db: Session = Depends(get_db)):
    return db.query(SearchCriteria).order_by(SearchCriteria.order.asc(), SearchCriteria.id.asc()).all()

@router.post("/reorder")
def reorder_search_criteria(ordered_ids: List[int], db: Session = Depends(get_db)):
    for index, criteria_id in enumerate(ordered_ids):
        db.query(SearchCriteria).filter(SearchCriteria.id == criteria_id).update({"order": index})
    db.commit()
    return {"message": "Order updated successfully."}

@router.post("", response_model=SearchCriteriaResponse)
def create_search_criteria(criteria_data: SearchCriteriaCreate, db: Session = Depends(get_db)):
    criteria = SearchCriteria(**criteria_data.model_dump())
    db.add(criteria)
    db.commit()
    db.refresh(criteria)
    return criteria

@router.put("/{criteria_id}", response_model=SearchCriteriaResponse)
def update_search_criteria(criteria_id: int, criteria_data: SearchCriteriaCreate, db: Session = Depends(get_db)):
    criteria = db.query(SearchCriteria).filter(SearchCriteria.id == criteria_id).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Search criteria not found.")
    for key, value in criteria_data.model_dump().items():
        setattr(criteria, key, value)
    db.commit()
    db.refresh(criteria)
    return criteria

@router.delete("/{criteria_id}")
def delete_search_criteria(criteria_id: int, db: Session = Depends(get_db)):
    criteria = db.query(SearchCriteria).filter(SearchCriteria.id == criteria_id).first()
    if not criteria:
        raise HTTPException(status_code=404, detail="Search criteria not found.")
    db.delete(criteria)
    db.commit()
    return {"message": "Search criteria deleted successfully."}
