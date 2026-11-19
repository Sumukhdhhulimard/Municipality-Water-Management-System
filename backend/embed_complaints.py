
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

from database import engine

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

print("Loading embedding model...")
model = SentenceTransformer(MODEL_NAME)

assert model.get_sentence_embedding_dimension() == 384

with engine.connect() as conn:
    complaints = conn.execute(text("""
        SELECT
            c.complaint_id,
            c.category,
            c.description
        FROM public.complaints c
        LEFT JOIN smart_water.complaint_embeddings e
            ON e.complaint_id = c.complaint_id
        WHERE e.complaint_id IS NULL
        ORDER BY c.complaint_id
    """)).mappings().all()

print("Complaints to embed:", len(complaints))

if complaints:
    texts = [
        f"Category: {row['category']}. "
        f"Description: {row['description']}"
        for row in complaints
    ]

    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32
    )

    with engine.begin() as conn:
        for row, content, vector in zip(
            complaints, texts, vectors
        ):
            conn.execute(text("""
                INSERT INTO smart_water.complaint_embeddings
                    (complaint_id, source_text, embedding)
                VALUES
                    (:id, :content, CAST(:embedding AS vector))
                ON CONFLICT (complaint_id)
                DO UPDATE SET
                    source_text = EXCLUDED.source_text,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
            """), {
                "id": row["complaint_id"],
                "content": content,
                "embedding": str(vector.tolist())
            })

print("Complaint embeddings generated successfully.")
