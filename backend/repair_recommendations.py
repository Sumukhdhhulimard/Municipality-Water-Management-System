
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from sentence_transformers import SentenceTransformer

from auth import require_role
from database import get_db

router = APIRouter(
    prefix="/operator/ai",
    tags=["Repair Recommendations"]
)

@lru_cache(maxsize=1)
def model():
    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )

@router.get("/repair-recommendations/{incident_id}")
def recommendations(
    incident_id: int,
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    incident = db.execute(text("""
        SELECT incident_type, description
        FROM smart_water.incidents
        WHERE incident_id = :id
    """), {"id": incident_id}).mappings().first()

    if not incident:
        raise HTTPException(404, "Incident not found")

    query = (
        f"Type: {incident['incident_type']}. "
        f"Problem: {incident['description']}"
    )

    vector = model().encode(
        query, normalize_embeddings=True
    ).tolist()

    matches = db.execute(text("""
        SELECT
            i.incident_id,
            i.incident_type,
            i.description,
            w.repair_notes,
            w.repair_cost,
            ROUND((
                1 - e.embedding <=>
                CAST(:vector AS vector)
            )::numeric, 4) AS similarity
        FROM smart_water.incident_embeddings e
        JOIN smart_water.incidents i
          ON i.incident_id = e.incident_id
        JOIN smart_water.work_orders w
          ON w.incident_id = i.incident_id
         AND w.status = 'COMPLETED'
        WHERE i.incident_id <> :id
          AND i.status = 'RESOLVED'
        ORDER BY
            e.embedding <=> CAST(:vector AS vector)
        LIMIT 5
    """), {
        "id": incident_id,
        "vector": str(vector)
    }).mappings().all()

    return {
        "incident_id": incident_id,
        "recommendations": [dict(m) for m in matches]
    }
