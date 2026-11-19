
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from mongo_database import mongo_db
from sync_incident_events import sync_incident_events

router = APIRouter(
    prefix="/operator/incidents",
    tags=["Incident History"]
)


@router.post("/sync-history")
def sync_history(
    user=Depends(require_role("operator"))
):
    return sync_incident_events()


@router.get("/{incident_id}/history")
def incident_history(
    incident_id: int,
    user=Depends(require_role("operator"))
):
    documents = mongo_db.incident_history.find(
        {"incident_id": incident_id},
        {"_id": 0}
    ).sort("created_at", 1)

    return list(documents)
