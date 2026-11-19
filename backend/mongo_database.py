
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING

load_dotenv()

client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://localhost:27017"),
    serverSelectionTimeoutMS=3000
)

mongo_db = client[
    os.getenv("MONGO_DB", "municipality_water_mongo")
]

def initialize_mongo():
    client.admin.command("ping")

    mongo_db.activity_logs.create_index([
        ("actor_role", ASCENDING),
        ("actor_id", ASCENDING)
    ])

    mongo_db.complaint_history.create_index(
        "complaint_id"
    )

    mongo_db.water_quality_reports.create_index([
        ("zone_id", ASCENDING),
        ("recorded_at", ASCENDING)
    ])

def log_activity(role, actor_id, action, details=None):
    return mongo_db.activity_logs.insert_one({
        "actor_role": role,
        "actor_id": actor_id,
        "action": action,
        "details": details or {},
        "created_at": datetime.now(timezone.utc)
    })

def record_complaint_history(
    complaint_id, operator_id, status, remark=""
):
    return mongo_db.complaint_history.insert_one({
        "complaint_id": complaint_id,
        "operator_id": operator_id,
        "status": status,
        "remark": remark,
        "updated_at": datetime.now(timezone.utc)
    })
