
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from incident_service import detect_sensor_incidents

router = APIRouter(
    prefix="/operator/incidents",
    tags=["Incident Management"]
)


class AssignmentRequest(BaseModel):
    technician_id: int = Field(gt=0)


class CompletionRequest(BaseModel):
    repair_notes: str = Field(min_length=5)
    repair_cost: Decimal = Field(ge=0)


@router.post("/scan")
def scan_sensors(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    try:
        return detect_sensor_incidents(db)
    except Exception:
        db.rollback()
        raise


@router.get("")
def list_incidents(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    result = db.execute(text("""
        SELECT
            i.incident_id,
            i.zone_id,
            z.zone_name,
            i.incident_type,
            i.severity,
            i.description,
            i.status,
            i.created_at,
            w.work_order_id,
            t.full_name AS technician_name
        FROM smart_water.incidents i
        JOIN public.zones z
          ON z.zone_id = i.zone_id
        LEFT JOIN smart_water.work_orders w
          ON w.incident_id = i.incident_id
         AND w.status IN ('ASSIGNED', 'IN_PROGRESS')
        LEFT JOIN smart_water.technicians t
          ON t.technician_id = w.technician_id
        ORDER BY i.created_at DESC
        LIMIT 200
    """)).mappings().all()

    return [dict(row) for row in result]


@router.get("/technicians")
def list_technicians(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    result = db.execute(text("""
        SELECT technician_id, full_name,
               specialization, zone_id, is_available
        FROM smart_water.technicians
        ORDER BY technician_id
    """)).mappings().all()

    return [dict(row) for row in result]


@router.post("/{incident_id}/assign")
def assign_technician(
    incident_id: int,
    data: AssignmentRequest,
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    try:
        incident = db.execute(text("""
            SELECT incident_id, zone_id, status
            FROM smart_water.incidents
            WHERE incident_id = :id
            FOR UPDATE
        """), {"id": incident_id}).mappings().first()

        if incident is None:
            raise HTTPException(404, "Incident not found")

        if incident["status"] != "OPEN":
            raise HTTPException(
                409, "Incident is not open for assignment"
            )

        technician = db.execute(text("""
            SELECT technician_id, zone_id, is_available
            FROM smart_water.technicians
            WHERE technician_id = :id
            FOR UPDATE
        """), {"id": data.technician_id}).mappings().first()

        if technician is None:
            raise HTTPException(404, "Technician not found")

        if not technician["is_available"]:
            raise HTTPException(
                409, "Technician is unavailable"
            )

        if technician["zone_id"] != incident["zone_id"]:
            raise HTTPException(
                400, "Technician belongs to another zone"
            )

        work_order_id = db.execute(text("""
            INSERT INTO smart_water.work_orders
                (incident_id, technician_id)
            VALUES (:incident_id, :technician_id)
            RETURNING work_order_id
        """), {
            "incident_id": incident_id,
            "technician_id": data.technician_id
        }).scalar_one()

        db.execute(text("""
            UPDATE smart_water.incidents
            SET status = 'ASSIGNED'
            WHERE incident_id = :id
        """), {"id": incident_id})

        db.execute(text("""
            UPDATE smart_water.technicians
            SET is_available = FALSE
            WHERE technician_id = :id
        """), {"id": data.technician_id})

        db.commit()

        return {
            "message": "Technician assigned",
            "incident_id": incident_id,
            "work_order_id": work_order_id
        }

    except Exception:
        db.rollback()
        raise


@router.post("/{incident_id}/complete")
def complete_incident(
    incident_id: int,
    data: CompletionRequest,
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    try:
        incident = db.execute(text("""
            SELECT incident_id, status
            FROM smart_water.incidents
            WHERE incident_id = :id
            FOR UPDATE
        """), {"id": incident_id}).mappings().first()

        if incident is None:
            raise HTTPException(404, "Incident not found")

        if incident["status"] not in (
            "ASSIGNED", "IN_PROGRESS"
        ):
            raise HTTPException(
                409, "Incident cannot be completed"
            )

        order = db.execute(text("""
            SELECT work_order_id, technician_id
            FROM smart_water.work_orders
            WHERE incident_id = :id
              AND status IN ('ASSIGNED', 'IN_PROGRESS')
            FOR UPDATE
        """), {"id": incident_id}).mappings().first()

        if order is None:
            raise HTTPException(
                409, "No active work order"
            )

        db.execute(text("""
            UPDATE smart_water.work_orders
            SET status = 'COMPLETED',
                repair_notes = :notes,
                repair_cost = :cost,
                completed_at = NOW()
            WHERE work_order_id = :id
        """), {
            "notes": data.repair_notes,
            "cost": data.repair_cost,
            "id": order["work_order_id"]
        })

        db.execute(text("""
            UPDATE smart_water.incidents
            SET status = 'RESOLVED',
                resolved_at = NOW()
            WHERE incident_id = :id
        """), {"id": incident_id})

        db.execute(text("""
            UPDATE smart_water.technicians
            SET is_available = TRUE
            WHERE technician_id = :id
        """), {"id": order["technician_id"]})

        db.commit()

        return {
            "message": "Incident resolved",
            "incident_id": incident_id
        }

    except Exception:
        db.rollback()
        raise
