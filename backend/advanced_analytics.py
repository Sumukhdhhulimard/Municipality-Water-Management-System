
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pymongo.errors import PyMongoError

from database import get_db
from auth import require_role
from mongo_database import mongo_db

router = APIRouter(
    prefix="/operator/advanced",
    tags=["Advanced Analytics"]
)


@router.get("/overview")
def advanced_overview(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    meter_stats = db.execute(text("""
        SELECT
            COUNT(*) AS total_meters,
            COUNT(*) FILTER (
                WHERE meter_status = 'ACTIVE'
            ) AS active_meters
        FROM smart_water.meters
    """)).mappings().one()

    reading_stats = db.execute(text("""
        SELECT
            COUNT(*) AS total_readings,
            COUNT(DISTINCT meter_id) AS monitored_meters
        FROM smart_water.meter_readings
    """)).mappings().one()

    leak_stats = db.execute(text("""
        SELECT
            COUNT(*) AS possible_leak_events,
            COUNT(DISTINCT meter_id)
                AS affected_meters
        FROM smart_water.vw_leakage_detection
        WHERE anomaly_status = 'POSSIBLE_LEAK'
    """)).mappings().one()

    try:
        sensor_count = mongo_db.sensor_events.count_documents({})
    except PyMongoError:
        raise HTTPException(
            status_code=503,
            detail="MongoDB sensor data unavailable"
        )

    return {
        "meters": dict(meter_stats),
        "readings": dict(reading_stats),
        "leakage": dict(leak_stats),
        "sensor_events": sensor_count
    }


@router.get("/leakage")
def leakage_alerts(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    result = db.execute(text("""
        SELECT
            m.meter_serial,
            m.connection_id,
            l.meter_id,
            l.reading_date,
            l.consumption_liters,
            l.baseline_liters,
            l.anomaly_status
        FROM smart_water.vw_leakage_detection l
        JOIN smart_water.meters m
          ON m.meter_id = l.meter_id
        WHERE l.anomaly_status = 'POSSIBLE_LEAK'
        ORDER BY l.reading_date DESC, l.meter_id
        LIMIT 100
    """)).mappings().all()

    return [
        {
            **dict(row),
            "reading_date": row["reading_date"].isoformat(),
            "consumption_liters": float(
                row["consumption_liters"]
            ),
            "baseline_liters": float(
                row["baseline_liters"]
            )
        }
        for row in result
    ]


@router.get("/consumption")
def consumption_summary(
    user=Depends(require_role("operator")),
    db: Session = Depends(get_db)
):
    result = db.execute(text("""
        SELECT
            m.connection_id,
            m.meter_serial,
            COUNT(*) AS reading_days,
            ROUND(
                SUM(d.consumption_liters), 2
            ) AS total_liters,
            ROUND(
                AVG(d.consumption_liters), 2
            ) AS average_daily_liters
        FROM smart_water.vw_daily_consumption d
        JOIN smart_water.meters m
          ON m.meter_id = d.meter_id
        GROUP BY m.connection_id, m.meter_serial
        ORDER BY total_liters DESC
        LIMIT 100
    """)).mappings().all()

    return [
        {
            **dict(row),
            "total_liters": float(row["total_liters"]),
            "average_daily_liters": float(
                row["average_daily_liters"]
            )
        }
        for row in result
    ]


@router.get("/water-quality")
def water_quality_summary(
    user=Depends(require_role("operator"))
):
    pipeline = [
        {
            "$group": {
                "_id": "$sensor.zone_id",
                "total_readings": {"$sum": 1},
                "average_ph": {"$avg": "$ph"},
                "average_turbidity": {
                    "$avg": "$turbidity_ntu"
                },
                "average_chlorine": {
                    "$avg": "$chlorine_mg_l"
                },
                "abnormal_count": {
                    "$sum": {
                        "$cond": [
                            {
                                "$or": [
                                    {"$lt": ["$ph", 6.5]},
                                    {"$gt": ["$ph", 8.5]},
                                    {
                                        "$gt": [
                                            "$turbidity_ntu", 2.0
                                        ]
                                    },
                                    {
                                        "$lt": [
                                            "$chlorine_mg_l", 0.2
                                        ]
                                    }
                                ]
                            },
                            1,
                            0
                        ]
                    }
                }
            }
        },
        {"$sort": {"_id": 1}}
    ]

    try:
        data = list(
            mongo_db.sensor_events.aggregate(pipeline)
        )
    except PyMongoError:
        raise HTTPException(
            status_code=503,
            detail="MongoDB sensor aggregation failed"
        )

    return [
        {
            "zone_id": row["_id"],
            "total_readings": row["total_readings"],
            "average_ph": round(
                row["average_ph"], 2
            ),
            "average_turbidity": round(
                row["average_turbidity"], 2
            ),
            "average_chlorine": round(
                row["average_chlorine"], 2
            ),
            "abnormal_count": row["abnormal_count"]
        }
        for row in data
    ]
