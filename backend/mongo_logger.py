
import os
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://localhost:27017"),
    serverSelectionTimeoutMS=3000
)

db = client[
    os.getenv("MONGO_DB", "water_management_mongo")
]

def log_complaint_update(
    complaint_id,
    operator_id,
    old_status,
    new_status
):
    document = {
        "complaint_id": int(complaint_id),
        "operator_id": int(operator_id),
        "old_status": old_status,
        "new_status": new_status,
        "updated_at": datetime.now(timezone.utc)
    }

    result = db.complaint_history.insert_one(document)
    return str(result.inserted_id)
