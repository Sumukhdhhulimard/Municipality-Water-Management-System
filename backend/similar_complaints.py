
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from database import get_db
from auth import require_role

router = APIRouter(
    prefix="/operator/ai",
    tags=["Intelligent Complaints"]
)

class SimilarComplaintRequest(BaseModel):
    description: str = Field(min_length=5, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)

@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

@router.post("/similar-complaints")
def similar_complaints(
    data: SimilarComplaintRequest,
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    model = get_model()

    vector = model.encode(
        data.description,
        normalize_embeddings=True
    ).tolist()

    results = db.execute(text("""
        SELECT
            c.complaint_id,
            c.category,
            c.description,
            c.status,
            ROUND(
                (
                    1 - (
                        e.embedding <=>
                        CAST(:embedding AS vector)
                    )
                )::numeric,
                4
            ) AS similarity
        FROM smart_water.complaint_embeddings e
        JOIN public.complaints c
            ON c.complaint_id = e.complaint_id
        ORDER BY
            e.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """), {
        "embedding": str(vector),
        "limit": data.limit
    }).mappings().all()

    return {
        "query": data.description,
        "total_matches": len(results),
        "matches": [dict(row) for row in results]
    }
