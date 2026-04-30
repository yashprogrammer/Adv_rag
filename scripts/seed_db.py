"""Idempotent database seeding script.

Usage:
    python scripts/seed_db.py
"""

import os

import psycopg2
from loguru import logger

from app.middleware.auth import hash_password

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/adv_rag")

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "seed", "migrations")

DEMO_USERS = [
    ("agent@demo.local", "agent123", False),
    ("admin@demo.local", "admin123", True),
]


def run_migrations(conn: psycopg2.extensions.connection) -> None:
    cur = conn.cursor()
    files = sorted([f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")])
    for filename in files:
        path = os.path.join(MIGRATIONS_DIR, filename)
        with open(path) as f:
            sql = f.read()
        logger.info("Running migration: {}", filename)
        cur.execute(sql)
    conn.commit()
    cur.close()


def seed_users(conn: psycopg2.extensions.connection) -> None:
    cur = conn.cursor()
    for username, password, is_admin in DEMO_USERS:
        password_hash = hash_password(password)
        cur.execute(
            """
            INSERT INTO users (username, password_hash, is_admin)
            VALUES (%s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                is_admin = EXCLUDED.is_admin
            """,
            (username, password_hash, is_admin),
        )
        logger.info("Seeded user: {} (admin={})", username, is_admin)
    conn.commit()
    cur.close()


def main() -> None:
    logger.info("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    logger.info("Running migrations...")
    run_migrations(conn)
    logger.info("Seeding demo users...")
    seed_users(conn)
    conn.close()
    logger.info("Done.")


def seed_docs() -> None:
    import glob

    from app.models import RetrievedChunk
    from app.services.document_processor import DocumentProcessor
    from app.services.embedding_service import embed_texts
    from app.services.vector_store import upsert_chunks

    processor = DocumentProcessor()
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "seed", "docs")
    for path in glob.glob(os.path.join(docs_dir, "*.txt")):
        logger.info("Ingesting seed doc: {}", path)
        chunks_meta = processor.process_document(path)
        chunks = [RetrievedChunk(text=c["text"], source=c["source"]) for c in chunks_meta]
        if chunks:
            texts = [c.text for c in chunks]
            embeddings = embed_texts(texts)
            upsert_chunks(chunks, embeddings)


if __name__ == "__main__":
    main()
    seed_docs()


if __name__ == "__main__":
    main()
