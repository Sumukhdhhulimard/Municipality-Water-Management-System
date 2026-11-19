
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
from pgvector.sqlalchemy import Vector

from database import engine

model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

knowledge = [
    (
        "New Water Connection",
        "Connections",
        "A new resident must register an account, "
        "provide address information, and submit a "
        "new water connection request. A municipality "
        "operator reviews the application."
    ),
    (
        "Connection Approval",
        "Connections",
        "New water connection requests are initially "
        "pending. An operator can approve or reject "
        "the request."
    ),
    (
        "Monthly Water Billing",
        "Billing",
        "Water bills are calculated using consumption "
        "units. In this demonstration, each unit costs "
        "12 Indian rupees."
    ),
    (
        "Bill Payment",
        "Payments",
        "Residents can view unpaid bills and complete "
        "simulated payments through their dashboard. "
        "Paid bills cannot be paid again."
    ),
    (
        "Payment History",
        "Payments",
        "Residents can view their previous water bill "
        "payments, transaction references, and amounts."
    ),
    (
        "Water Leakage Complaint",
        "Complaints",
        "Residents can report leaking water pipes "
        "through the complaints section. Operators "
        "review and update the complaint status."
    ),
    (
        "Low Water Pressure",
        "Complaints",
        "Residents experiencing low water pressure "
        "can submit a complaint with details about "
        "the affected location."
    ),
    (
        "Water Quality Complaint",
        "Complaints",
        "Residents can report unusual water color, "
        "odor, or suspected contamination. Such "
        "reports require municipal investigation."
    ),
    (
        "Complaint Tracking",
        "Complaints",
        "Residents can track complaints as Open, "
        "In Progress, or Resolved."
    ),
    (
        "Water Conservation",
        "Conservation",
        "Residents can conserve water by repairing "
        "leaks, avoiding unnecessary water usage, "
        "and monitoring consumption."
    ),
    (
        "Operator Responsibilities",
        "Operations",
        "Municipality operators manage connection "
        "requests, complaints, billing records, "
        "and payment monitoring."
    ),
    (
        "Water Quality Monitoring",
        "Monitoring",
        "Municipality operators can review zone-wise "
        "water quality reports containing pH, "
        "turbidity, and chlorine measurements."
    )
]

with engine.begin() as conn:
    for title, category, content in knowledge:
        vector = model.encode(
            title + ". " + content,
            normalize_embeddings=True
        ).tolist()

        existing = conn.execute(text("""
            SELECT knowledge_id
            FROM water_knowledge
            WHERE title = :title
        """), {"title": title}).scalar_one_or_none()

        if existing:
            conn.execute(text("""
                UPDATE water_knowledge
                SET category = :category,
                    content = :content,
                    embedding = CAST(:embedding AS vector)
                WHERE knowledge_id = :id
            """), {
                "id": existing,
                "category": category,
                "content": content,
                "embedding": str(vector)
            })
        else:
            conn.execute(text("""
                INSERT INTO water_knowledge
                (title, category, content, embedding)
                VALUES (
                    :title, :category, :content,
                    CAST(:embedding AS vector)
                )
            """), {
                "title": title,
                "category": category,
                "content": content,
                "embedding": str(vector)
            })

print("Knowledge records prepared:", len(knowledge))
