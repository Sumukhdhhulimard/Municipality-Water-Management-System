
from sqlalchemy import text
from sqlalchemy.orm import Session

from mongo_database import mongo_db


def classify_reading(doc):
    ph = doc.get("ph")
    turbidity = doc.get("turbidity_ntu")
    chlorine = doc.get("chlorine_mg_l")

    problems = []

    if isinstance(ph, (int, float)):
        if ph < 6.5 or ph > 8.5:
            problems.append("pH outside configured range")

    if isinstance(turbidity, (int, float)):
        if turbidity > 2.0:
            problems.append("Elevated turbidity")

    if isinstance(chlorine, (int, float)):
        if chlorine < 0.2:
            problems.append("Low chlorine reading")

    if not problems:
        return None

    return {
        "incident_type": "WATER_QUALITY",
        "severity": "HIGH",
        "description": "; ".join(problems)
    }


def detect_sensor_incidents(db: Session):
    query = {
        "$or": [
            {"ph": {"$lt": 6.5}},
            {"ph": {"$gt": 8.5}},
            {"turbidity_ntu": {"$gt": 2.0}},
            {"chlorine_mg_l": {"$lt": 0.2}}
        ]
    }

    valid_zones = set(
        db.execute(text(
            "SELECT zone_id FROM public.zones"
        )).scalars().all()
    )

    created = 0
    already_processed = 0
    skipped = 0

    for doc in mongo_db.sensor_events.find(query):
        event_id = str(doc["_id"])
        zone_id = doc.get("sensor", {}).get("zone_id")

        if zone_id not in valid_zones:
            skipped += 1
            continue

        classification = classify_reading(doc)

        if classification is None:
            skipped += 1
            continue

        with db.begin_nested():
            inserted = db.execute(text("""
                INSERT INTO smart_water.incidents (
                    zone_id,
                    incident_type,
                    severity,
                    description,
                    source,
                    source_event_id
                )
                VALUES (
                    :zone_id,
                    :incident_type,
                    :severity,
                    :description,
                    'SENSOR',
                    :event_id
                )
                ON CONFLICT (source_event_id)
                DO NOTHING
                RETURNING incident_id
            """), {
                "zone_id": zone_id,
                "incident_type": classification["incident_type"],
                "severity": classification["severity"],
                "description": classification["description"],
                "event_id": event_id
            }).scalar_one_or_none()

        if inserted is None:
            already_processed += 1
        else:
            created += 1

    db.commit()

    return {
        "created": created,
        "already_processed": already_processed,
        "skipped": skipped
    }
