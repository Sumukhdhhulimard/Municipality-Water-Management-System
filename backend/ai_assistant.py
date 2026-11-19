
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from database import get_db
from auth import current_user

router = APIRouter(prefix="/ai", tags=["AI Assistant"])

@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

class Question(BaseModel):
    question: str = Field(min_length=3, max_length=1000)

@router.post("/ask")
def ask_question(
    data: Question,
    user=Depends(current_user),
    db: Session = Depends(get_db)
):
    embedding = get_model().encode(
        data.question,
        normalize_embeddings=True
    ).tolist()

    results = db.execute(text("""
        SELECT title, category, content,
               1 - (embedding <=> CAST(:vector AS vector))
               AS similarity
        FROM water_knowledge
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:vector AS vector)
        LIMIT 3
    """), {
        "vector": str(embedding)
    }).mappings().all()

    matches = [
        {
            "title": row["title"],
            "category": row["category"],
            "content": row["content"],
            "similarity": round(float(row["similarity"]), 3)
        }
        for row in results
        if row["similarity"] is not None
        and row["similarity"] >= 0.35
    ]

    if not matches:
        return {
            "answer": "No sufficiently relevant guidance found.",
            "sources": []
        }

    return {
        "answer": matches[0]["content"],
        "sources": matches
    }
