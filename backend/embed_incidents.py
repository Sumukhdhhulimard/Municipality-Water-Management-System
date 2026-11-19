
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from database import engine

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT
            i.incident_id,
            i.incident_type,
            i.description,
            w.repair_notes
        FROM smart_water.incidents i
        JOIN smart_water.work_orders w
          ON w.incident_id = i.incident_id
        WHERE i.status = 'RESOLVED'
          AND w.status = 'COMPLETED'
          AND w.repair_notes IS NOT NULL
    """)).mappings().all()

with engine.begin() as conn:
    for row in rows:
        content = (
            f"Type: {row['incident_type']}. "
            f"Problem: {row['description']}"
        )

        vector = model.encode(
            content,
            normalize_embeddings=True
        ).tolist()

        conn.execute(text("""
            INSERT INTO smart_water.incident_embeddings
                (incident_id, embedding, source_text)
            VALUES (
                :id,
                CAST(:embedding AS vector),
                :content
            )
            ON CONFLICT (incident_id)
            DO UPDATE SET
                embedding = EXCLUDED.embedding,
                source_text = EXCLUDED.source_text,
                updated_at = NOW()
        """), {
            "id": row["incident_id"],
            "embedding": str(vector),
            "content": content
        })

print(f"Indexed {len(rows)} resolved incidents.")
