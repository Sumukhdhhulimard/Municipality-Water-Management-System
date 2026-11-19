
from sqlalchemy import text
from database import SessionLocal
from auth import hash_password

db = SessionLocal()

try:
    resident_hash = hash_password("Resident@123")
    operator_hash = hash_password("Operator@123")

    db.execute(text("""
        UPDATE residents
        SET password_hash = :hash
        WHERE password_hash = 'PENDING_HASH'
    """), {"hash": resident_hash})

    db.execute(text("""
        UPDATE operators
        SET password_hash = :hash
        WHERE password_hash = 'PENDING_HASH'
    """), {"hash": operator_hash})

    db.commit()
    print("Demo credentials initialized successfully")

except Exception:
    db.rollback()
    raise
finally:
    db.close()
