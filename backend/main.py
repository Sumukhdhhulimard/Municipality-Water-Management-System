
from datetime import date
from decimal import Decimal
from typing import Literal

from similar_complaints import router as similar_complaints_router




from mongo_database import record_complaint_history

from advanced_analytics import router as advanced_router

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db
from auth import (
    hash_password, verify_password,
    create_token, require_role
)

from ai_assistant import router as ai_router


from incident_router import router as incident_router

from incident_extras import router as incident_extras_router


from repair_recommendations import router as repair_router




app = FastAPI(title="Municipality Water Management")
app.include_router(ai_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
app.include_router(similar_complaints_router)
app.include_router(incident_extras_router)
app.include_router(incident_router)
app.include_router(repair_router)

app.include_router(advanced_router)

class Register(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str | None = None
    road_id: int | None = None
    house_number: str | None = None


class Login(BaseModel):
    email: str = Field(min_length=3)
    password: str


class ConnectionRequest(BaseModel):
    connection_type: Literal["Domestic", "Commercial"] = "Domestic"

class ComplaintRequest(BaseModel):
    category: str = Field(min_length=3, max_length=50)
    description: str = Field(min_length=5)
    connection_id: int | None = None

class PaymentRequest(BaseModel):
    method: Literal["UPI", "Card", "Cash", "Demo"] = "Demo"

class StatusUpdate(BaseModel):
    status: Literal["Approved", "Rejected"]

class ComplaintUpdate(BaseModel):
    status: Literal["Open", "In Progress", "Resolved"]

def rows(result):
    return [dict(row) for row in result.mappings().all()]

@app.get("/")
def home():
    return {"message": "Municipality Water API running"}

@app.get("/locations")
def locations(db: Session = Depends(get_db)):
    return rows(db.execute(text("""
        SELECT rd.road_id, rd.road_name,
               z.zone_id, z.zone_name
        FROM roads rd
        JOIN zones z ON z.zone_id = rd.zone_id
        ORDER BY z.zone_id, rd.road_id
    """)))

@app.post("/register", status_code=201)
def register(data: Register, db: Session = Depends(get_db)):
    existing = db.execute(text("""
        SELECT 1 FROM residents WHERE email = :email
        UNION ALL
        SELECT 1 FROM operators WHERE email = :email
    """), {"email": str(data.email).lower()}).first()

    if existing:
        raise HTTPException(409, "Email already registered")

    if data.road_id is not None:
        road = db.execute(text("""
            SELECT 1 FROM roads WHERE road_id = :id
        """), {"id": data.road_id}).first()
        if not road:
            raise HTTPException(400, "Invalid road ID")

    result = db.execute(text("""
        INSERT INTO residents
        (full_name, email, password_hash, phone,
         road_id, house_number)
        VALUES (:name, :email, :password, :phone,
                :road, :house)
        RETURNING resident_id
    """), {
        "name": data.full_name,
        "email": str(data.email).lower(),
        "password": hash_password(data.password),
        "phone": data.phone,
        "road": data.road_id,
        "house": data.house_number
    })
    resident_id = result.scalar_one()
    db.commit()
    return {"resident_id": resident_id, "message": "Registered"}

@app.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    email = str(data.email).lower()

    for table, id_column, role in [
        ("residents", "resident_id", "resident"),
        ("operators", "operator_id", "operator")
    ]:
        user = db.execute(text(f"""
            SELECT {id_column} AS id, password_hash
            FROM {table}
            WHERE email = :email
        """), {"email": email}).mappings().first()

        if user and verify_password(
            data.password, user["password_hash"]
        ):
            return {
                "access_token": create_token(user["id"], role),
                "token_type": "bearer",
                "role": role,
                "user_id": user["id"]
            }

    raise HTTPException(401, "Invalid credentials")


@app.get("/resident/dashboard")
def resident_dashboard(
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    resident = db.execute(text("""
        SELECT
            r.resident_id,
            r.full_name,
            r.email,
            r.phone,
            r.house_number,
            r.road_id,
            rd.road_name,
            z.zone_name
        FROM residents r
        LEFT JOIN roads rd
            ON rd.road_id = r.road_id
        LEFT JOIN zones z
            ON z.zone_id = rd.zone_id
        WHERE r.resident_id = :id
    """), {"id": user["id"]}).mappings().first()

    if not resident:
        raise HTTPException(
            status_code=404,
            detail="Resident not found"
        )

    connections = rows(db.execute(text("""
        SELECT
            connection_id,
            connection_type,
            status
        FROM water_connections
        WHERE resident_id = :id
        ORDER BY connection_id DESC
    """), {"id": user["id"]}))

    return {
        **dict(resident),
        "connections": connections
    }

@app.post("/resident/connections", status_code=201)
def request_connection(
    data: ConnectionRequest,
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    existing = db.execute(text("""
        SELECT 1 FROM water_connections
        WHERE resident_id = :id
        AND status IN ('Pending', 'Approved')
    """), {"id": user["id"]}).first()

    if existing:
        raise HTTPException(409, "Active or pending connection exists")

    result = db.execute(text("""
        INSERT INTO water_connections
        (resident_id, connection_type, status)
        VALUES (:id, :type, 'Pending')
        RETURNING connection_id
    """), {
        "id": user["id"],
        "type": data.connection_type
    })
    connection_id = result.scalar_one()
    db.commit()
    return {"connection_id": connection_id, "status": "Pending"}

@app.get("/resident/connections")
def my_connections(
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT * FROM water_connections
        WHERE resident_id = :id
        ORDER BY connection_id DESC
    """), {"id": user["id"]}))

@app.get("/resident/bills")
def my_bills(
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT b.*
        FROM bills b
        JOIN water_connections c
          ON c.connection_id = b.connection_id
        WHERE c.resident_id = :id
        ORDER BY b.billing_month DESC, b.bill_id DESC
    """), {"id": user["id"]}))

@app.post("/resident/bills/{bill_id}/pay")
def pay_bill(
    bill_id: int,
    data: PaymentRequest,
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    import uuid

    try:
        # Lock the bill before checking ownership and payment.
        bill = db.execute(text("""
            SELECT b.bill_id, b.status
            FROM bills b
            JOIN water_connections c
              ON c.connection_id = b.connection_id
            WHERE b.bill_id = :bill_id
              AND c.resident_id = :resident_id
            FOR UPDATE OF b
        """), {
            "bill_id": bill_id,
            "resident_id": user["id"]
        }).mappings().first()

        if not bill:
            raise HTTPException(404, "Bill not found")

        if bill["status"] == "Paid":
            raise HTTPException(409, "Bill already paid")

        reference = "DEMO-" + uuid.uuid4().hex[:20]

        payment_id = db.execute(text("""
            SELECT pay_water_bill(
                :bill_id, :method, :reference
            )
        """), {
            "bill_id": bill_id,
            "method": data.method,
            "reference": reference
        }).scalar_one()

        db.commit()
        return {
            "message": "Simulated payment successful",
            "payment_id": payment_id,
            "reference": reference
        }
    except Exception:
        db.rollback()
        raise

@app.get("/resident/payments")
def my_payments(
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT p.*
        FROM payments p
        JOIN bills b ON b.bill_id = p.bill_id
        JOIN water_connections c
          ON c.connection_id = b.connection_id
        WHERE c.resident_id = :id
        ORDER BY p.paid_at DESC
    """), {"id": user["id"]}))

@app.post("/resident/complaints", status_code=201)
def create_complaint(
    data: ComplaintRequest,
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    if data.connection_id is not None:
        owned = db.execute(text("""
            SELECT 1 FROM water_connections
            WHERE connection_id = :cid
              AND resident_id = :rid
        """), {
            "cid": data.connection_id,
            "rid": user["id"]
        }).first()
        if not owned:
            raise HTTPException(403, "Connection not owned by resident")

    result = db.execute(text("""
        INSERT INTO complaints
        (resident_id, connection_id, category, description)
        VALUES (:rid, :cid, :category, :description)
        RETURNING complaint_id
    """), {
        "rid": user["id"],
        "cid": data.connection_id,
        "category": data.category,
        "description": data.description
    })
    complaint_id = result.scalar_one()
    db.commit()
    return {"complaint_id": complaint_id, "status": "Open"}

@app.get("/resident/complaints")
def my_complaints(
    user=Depends(require_role("resident")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT * FROM complaints
        WHERE resident_id = :id
        ORDER BY created_at DESC
    """), {"id": user["id"]}))

@app.get("/operator/dashboard")
def operator_dashboard(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    operator = db.execute(text("""
        SELECT operator_id, full_name, zone_id
        FROM operators WHERE operator_id = :id
    """), {"id": user["id"]}).mappings().first()

    if not operator:
        raise HTTPException(404, "Operator not found")

    stats = db.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM residents) AS residents,
          (SELECT COUNT(*) FROM water_connections
           WHERE status = 'Pending') AS pending_connections,
          (SELECT COUNT(*) FROM complaints
           WHERE status <> 'Resolved') AS active_complaints,
          (SELECT COUNT(*) FROM payments) AS total_payments,
          (SELECT COALESCE(SUM(amount),0)
           FROM payments) AS revenue
    """)).mappings().one()

    return {"operator": dict(operator), "stats": dict(stats)}


@app.get("/operator/residents")
def all_residents(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT
            r.resident_id,
            r.full_name,
            r.email,
            r.phone,
            rd.road_name,
            z.zone_name,
            c.connection_id,
            c.connection_type,
            c.status AS connection_status
        FROM residents r
        LEFT JOIN roads rd
            ON rd.road_id = r.road_id
        LEFT JOIN zones z
            ON z.zone_id = rd.zone_id
        LEFT JOIN water_connections c
            ON c.resident_id = r.resident_id
        ORDER BY r.resident_id, c.connection_id
    """)))


@app.get("/operator/connections")
def all_connections(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT c.*, r.full_name, r.email
        FROM water_connections c
        JOIN residents r ON r.resident_id = c.resident_id
        ORDER BY c.connection_id DESC
    """)))

@app.get("/operator/approved-connections")
def approved_connections(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT
            c.connection_id,
            c.resident_id,
            r.full_name,
            r.email,
            c.connection_type,
            c.status
        FROM water_connections c
        JOIN residents r
            ON r.resident_id = c.resident_id
        WHERE c.status = 'Approved'
        ORDER BY r.full_name, c.connection_id
    """)))

@app.patch("/operator/connections/{connection_id}")
def update_connection(
    connection_id: int,
    data: StatusUpdate,
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    result = db.execute(text("""
        UPDATE water_connections
        SET status = :status
        WHERE connection_id = :id AND status = 'Pending'
        RETURNING connection_id
    """), {"status": data.status, "id": connection_id})

    if not result.first():
        db.rollback()
        raise HTTPException(409, "No pending connection found")

    db.commit()
    return {"message": "Connection updated", "status": data.status}

@app.get("/operator/complaints")
def all_complaints(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT cp.*, r.full_name
        FROM complaints cp
        JOIN residents r ON r.resident_id = cp.resident_id
        ORDER BY cp.created_at DESC
    """)))

@app.patch("/operator/complaints/{complaint_id}")
def update_complaint(
    complaint_id: int,
    data: ComplaintUpdate,
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    # Lock the record to prevent concurrent status changes.
    complaint = db.execute(text("""
        SELECT status FROM complaints
        WHERE complaint_id = :id
        FOR UPDATE
    """), {"id": complaint_id}).mappings().first()

    if complaint is None:
        db.rollback()
        raise HTTPException(404, "Complaint not found")

    old_status = complaint["status"]
    if old_status == data.status:
        db.rollback()
        return {"message": "Status unchanged", "status": data.status}

    try:
        db.execute(text("""
            UPDATE complaints SET status = :status
            WHERE complaint_id = :id
        """), {"status": data.status, "id": complaint_id})
        db.commit()
    except Exception:
        db.rollback()
        raise

    # MongoDB audit logging occurs after the PostgreSQL commit.
    # Failure is reported explicitly so it is not mistaken for success.
    try:
        record_complaint_history(
            complaint_id=complaint_id,
            operator_id=user["id"],
            status=data.status,
            remark=f"Status changed from {old_status} to {data.status}"
        )
        history_logged = True
    except Exception:
        import logging
        logging.exception("MongoDB complaint history write failed")
        history_logged = False

    return {
        "message": "Complaint updated",
        "status": data.status,
        "history_logged": history_logged,
    }

@app.get("/operator/payments")
def all_payments(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT p.*, r.full_name, r.resident_id
        FROM payments p
        JOIN bills b ON b.bill_id = p.bill_id
        JOIN water_connections c
          ON c.connection_id = b.connection_id
        JOIN residents r ON r.resident_id = c.resident_id
        ORDER BY p.paid_at DESC
    """)))

@app.get("/operator/zones")
def zone_statistics(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT * FROM vw_zone_complaints
        ORDER BY zone_id
    """)))

from datetime import timedelta
from sqlalchemy.exc import IntegrityError

class MeterReading(BaseModel):
    connection_id: int = Field(gt=0)
    billing_month: date
    units_consumed: Decimal = Field(ge=0, le=100000)

@app.post("/operator/generate-bill", status_code=201)
def generate_bill(
    data: MeterReading,
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    if data.billing_month.day != 1:
        raise HTTPException(
            400, "Billing month must be the first day of a month"
        )

    connection = db.execute(text("""
        SELECT connection_id
        FROM water_connections
        WHERE connection_id = :id
          AND status = 'Approved'
    """), {"id": data.connection_id}).first()

    if not connection:
        raise HTTPException(
            404, "Approved connection not found"
        )

    next_month = (
        data.billing_month.replace(day=28)
        + timedelta(days=4)
    ).replace(day=1)

    due_date = next_month + timedelta(days=19)

    try:
        result = db.execute(text("""
            INSERT INTO bills (
                connection_id,
                billing_month,
                units_consumed,
                amount,
                due_date,
                status
            )
            VALUES (
                :connection_id,
                :billing_month,
                :units,
                calculate_water_bill(:units),
                :due_date,
                'Unpaid'
            )
            RETURNING bill_id, amount
        """), {
            "connection_id": data.connection_id,
            "billing_month": data.billing_month,
            "units": data.units_consumed,
            "due_date": due_date
        }).mappings().one()

        db.commit()

        return {
            "message": "Bill generated successfully",
            "bill_id": result["bill_id"],
            "amount": result["amount"]
        }

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Bill already exists for this connection and month"
        )

@app.get("/operator/bills")
def operator_bills(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    return rows(db.execute(text("""
        SELECT b.bill_id, b.connection_id,
               r.resident_id, r.full_name,
               b.billing_month, b.units_consumed,
               b.amount, b.due_date, b.status
        FROM bills b
        JOIN water_connections c
          ON c.connection_id = b.connection_id
        JOIN residents r
          ON r.resident_id = c.resident_id
        ORDER BY b.bill_id DESC
    """)))

from mongo_database import mongo_db

@app.get("/operator/water-quality")
def water_quality_reports(
    zone_id: int | None = None,
    user=Depends(require_role("operator"))
):
    query = {}
    if zone_id is not None:
        query["zone_id"] = zone_id

    documents = mongo_db.water_quality_reports.find(
        query,
        {"_id": 0}
    ).sort("recorded_at", -1).limit(200)

    return list(documents)

@app.get("/operator/activity-logs")
def activity_logs(
    user=Depends(require_role("operator"))
):
    documents = mongo_db.activity_logs.find(
        {},
        {"_id": 0}
    ).sort("created_at", -1).limit(100)

    return list(documents)

@app.get("/operator/complaint-history/{complaint_id}")
def complaint_history(
    complaint_id: int,
    user=Depends(require_role("operator"))
):
    documents = mongo_db.complaint_history.find(
        {"complaint_id": complaint_id},
        {"_id": 0}
    ).sort("updated_at", -1)

    return list(documents)
