
from sqlalchemy import text

from database import engine
from mongo_database import mongo_db

with engine.connect() as connection:
    zones = connection.execute(text("""
        SELECT zone_id, zone_name
        FROM zones
        ORDER BY zone_id
    """)).mappings().all()

updated = 0

for zone in zones:
    result = mongo_db.water_quality_reports.update_many(
        {"zone_id": zone["zone_id"]},
        {
            "$set": {
                "zone_name": zone["zone_name"]
            }
        }
    )

    updated += result.modified_count

    print(
        zone["zone_id"],
        zone["zone_name"],
        "Updated:",
        result.modified_count
    )

print("Total modified reports:", updated)
