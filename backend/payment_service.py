
from uuid import uuid4
from sqlalchemy import text
from fastapi import HTTPException


def pay_water_bill(db, resident_id, bill_id):
    try:
        bill = db.execute(
            text("""
                SELECT
                    b.bill_id,
                    b.amount,
                    b.status
                FROM bills b
                JOIN water_connections c
                  ON c.connection_id = b.connection_id
                WHERE b.bill_id = :bill_id
                  AND c.resident_id = :resident_id
                FOR UPDATE OF b
            """),
            {
                "bill_id": bill_id,
                "resident_id": resident_id
            }
        ).mappings().first()

        if not bill:
            raise HTTPException(
                status_code=404,
                detail="Bill not found"
            )

        if bill["status"] != "Unpaid":
            raise HTTPException(
                status_code=409,
                detail="Bill is already paid or unavailable"
            )

        reference = "DEMO-" + uuid4().hex[:16]

        payment = db.execute(
            text("""
                INSERT INTO payments (
                    bill_id,
                    amount,
                    payment_method,
                    transaction_reference
                )
                VALUES (
                    :bill_id,
                    :amount,
                    'Demo Payment',
                    :reference
                )
                RETURNING payment_id
            """),
            {
                "bill_id": bill_id,
                "amount": bill["amount"],
                "reference": reference
            }
        ).scalar_one()

        db.execute(
            text("""
                UPDATE bills
                SET status = 'Paid'
                WHERE bill_id = :bill_id
            """),
            {"bill_id": bill_id}
        )

        db.commit()

        return {
            "message": "Payment successful",
            "payment_id": payment,
            "bill_id": bill_id,
            "amount": float(bill["amount"]),
            "transaction_reference": reference,
            "status": "Paid"
        }

    except Exception:
        db.rollback()
        raise
