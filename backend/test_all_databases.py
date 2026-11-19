
from sqlalchemy import text
from database import engine
from mongo_database import mongo_db, client


def test_postgresql():
    with engine.connect() as conn:
        residents = conn.execute(
            text("SELECT COUNT(*) FROM residents")
        ).scalar_one()

        bills = conn.execute(
            text("SELECT COUNT(*) FROM bills")
        ).scalar_one()

        payments = conn.execute(
            text("SELECT COUNT(*) FROM payments")
        ).scalar_one()

        print("\nPOSTGRESQL: CONNECTED")
        print("Residents:", residents)
        print("Bills:", bills)
        print("Payments:", payments)


def test_mongodb():
    client.admin.command("ping")

    reports = mongo_db.water_quality_reports.count_documents({})
    history = mongo_db.complaint_history.count_documents({})

    print("\nMONGODB: CONNECTED")
    print("Water quality reports:", reports)
    print("Complaint history records:", history)


def test_pgvector():
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(embedding) AS embedded,
                MIN(vector_dims(embedding)) AS min_dims,
                MAX(vector_dims(embedding)) AS max_dims
            FROM water_knowledge
        """)).mappings().one()

        print("\nPGVECTOR: QUERY SUCCESSFUL")
        print("Knowledge records:", result["total"])
        print("Embedded records:", result["embedded"])
        print("Minimum dimensions:", result["min_dims"])
        print("Maximum dimensions:", result["max_dims"])


if __name__ == "__main__":
    checks = [
        ("PostgreSQL", test_postgresql),
        ("MongoDB", test_mongodb),
        ("pgvector", test_pgvector)
    ]

    failed = []

    for name, check in checks:
        try:
            check()
        except Exception as error:
            failed.append(name)
            print(f"\n{name}: FAILED")
            print(type(error).__name__, str(error))

    if failed:
        print("\nFailed checks:", ", ".join(failed))
        raise SystemExit(1)

    print("\nALL DATABASE CONNECTION CHECKS PASSED")
