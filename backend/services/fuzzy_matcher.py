import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional
from sqlalchemy.orm import Session
from backend.models import QAEntry

def normalize(question: str) -> str:
    """
    Normalizes a question by lowercasing it, decomposing unicode characters
    (stripping accents), removing punctuation, and stripping extra whitespace.
    """
    if not question:
        return ""
    # Lowercase
    normalized = question.lower()
    # Remove accents/diacritics
    normalized = "".join(
        c for c in unicodedata.normalize("NFD", normalized)
        if unicodedata.category(c) != "Mn"
    )
    # Remove non-alphanumeric and extra symbols, leaving space
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    # Standardize whitespace to single spaces
    normalized = " ".join(normalized.split())
    return normalized

def calculate_similarity(s1: str, s2: str) -> float:
    return SequenceMatcher(None, s1, s2).ratio()

def exact_match(db: Session, question: str) -> Optional[QAEntry]:
    """
    Matches the normalized question exactly against normalized entries in the DB.
    """
    norm_q = normalize(question)
    if not norm_q:
        return None
    return db.query(QAEntry).filter(QAEntry.normalized_question == norm_q).first()

def fuzzy_match(db: Session, question: str, threshold: float = 1.0) -> Optional[QAEntry]:
    """
    Matches a question against normalized entries in the DB using fuzzy string distance.
    Returns the QAEntry with the highest score >= threshold, or None.
    """
    norm_q = normalize(question)
    if not norm_q:
        return None
    
    # Try exact match first for performance
    exact = exact_match(db, question)
    if exact:
        return exact

    # Retrieve all entries for comparison
    all_qa = db.query(QAEntry).all()
    best_score = 0.0
    best_match = None

    for qa in all_qa:
        score = calculate_similarity(norm_q, qa.normalized_question)
        if score > best_score:
            best_score = score
            best_match = qa

    if best_score >= threshold:
        return best_match
    return None
