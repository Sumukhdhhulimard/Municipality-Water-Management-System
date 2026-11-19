
from mongo_logger import db
from datetime import datetime, timezone

db.command("ping")

result = db.complaint_history.insert_one({
    "complaint_id": 99999,
    "operator_id": 1,
    "old_status": "Open",
    "new_status": "In Progress",
    "updated_at": datetime.now(timezone.utc),
    "test_record": True
})

print("MongoDB insert successful:", result.inserted_id)
