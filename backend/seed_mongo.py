
from datetime import datetime, timezone, timedelta
from random import Random

from mongo_database import mongo_db, initialize_mongo

initialize_mongo()

rng = Random(42)

reports = []

for zone_id in range(1, 6):
    for day in range(1, 31):
        reports.append({
            "report_key": f"zone-{zone_id}-day-{day}",
            "zone_id": zone_id,
            "zone_name": f"Zone {zone_id}",
            "recorded_at": datetime(
                2026, 10, 1, tzinfo=timezone.utc
            ) + timedelta(days=day - 1),
            "ph": round(rng.uniform(6.8, 8.2), 2),
            "turbidity_ntu": round(
                rng.uniform(0.2, 4.0), 2
            ),
            "chlorine_mg_l": round(
                rng.uniform(0.2, 0.8), 2
            ),
            "sample_type": "Synthetic",
            "source": "Demo water quality dataset"
        })

mongo_db.water_quality_reports.create_index(
    "report_key", unique=True
)

for report in reports:
    mongo_db.water_quality_reports.update_one(
        {"report_key": report["report_key"]},
        {"$set": report},
        upsert=True
    )

print("MongoDB synthetic reports ready:", len(reports))
