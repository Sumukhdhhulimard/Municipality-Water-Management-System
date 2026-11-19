
from datetime import timezone

from pymongo import UpdateOne
from sqlalchemy import text

from database import engine
from mongo_database import mongo_db


def sync_incident_events(batch_size=100):
    delivered = 0

    with engine.begin() as conn:
        events = conn.execute(text("""
            SELECT
                event_id,
                incident_id,
                event_type,
                payload,
                created_at
            FROM smart_water.incident_outbox
            WHERE delivered_at IS NULL
            ORDER BY event_id
            LIMIT :limit
            FOR UPDATE SKIP LOCKED
        """), {"limit": batch_size}).mappings().all()

        if not events:
            return {"delivered": 0, "pending_batch": 0}

        operations = []

        for event in events:
            created_at = event["created_at"]

            if created_at.tzinfo is None:
                created_at = created_at.replace(
                    tzinfo=timezone.utc
                )

            operations.append(
                UpdateOne(
                    {"event_id": event["event_id"]},
                    {
                        "$setOnInsert": {
                            "event_id": event["event_id"],
                            "incident_id": event["incident_id"],
                            "event_type": event["event_type"],
                            "payload": event["payload"],
                            "created_at": created_at
                        }
                    },
                    upsert=True
                )
            )

        mongo_db.incident_history.bulk_write(
            operations,
            ordered=True
        )

        ids = [event["event_id"] for event in events]

        conn.execute(text("""
            UPDATE smart_water.incident_outbox
            SET delivered_at = NOW(),
                attempts = attempts + 1
            WHERE event_id = ANY(:ids)
        """), {"ids": ids})

        delivered = len(ids)

    return {
        "delivered": delivered,
        "pending_batch": len(events)
    }


if __name__ == "__main__":
    print(sync_incident_events())
