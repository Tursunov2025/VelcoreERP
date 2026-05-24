import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./azmus_new.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Add new columns to existing SQLite tables when upgrading."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    migrations = [
        "ALTER TABLE orders ADD COLUMN operator_id INTEGER",
        "ALTER TABLE orders ADD COLUMN image_url VARCHAR",
        "ALTER TABLE orders ADD COLUMN created_at VARCHAR",
        "ALTER TABLE orders ADD COLUMN updated_at VARCHAR",
        "ALTER TABLE users ADD COLUMN password_hash VARCHAR",
        "ALTER TABLE users ADD COLUMN created_at VARCHAR",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
