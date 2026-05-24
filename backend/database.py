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
    if not DATABASE_URL.startswith("sqlite"):
        return

    migrations = [
        "ALTER TABLE orders ADD COLUMN operator_id INTEGER",
        "ALTER TABLE orders ADD COLUMN image_url VARCHAR",
        "ALTER TABLE orders ADD COLUMN created_at DATETIME",
        "ALTER TABLE orders ADD COLUMN updated_at DATETIME",
        "ALTER TABLE users ADD COLUMN password_hash VARCHAR",
        "ALTER TABLE users ADD COLUMN created_at DATETIME",
        "ALTER TABLE users ADD COLUMN department VARCHAR DEFAULT 'Kesish'",
        "ALTER TABLE orders ADD COLUMN comment TEXT",
        "ALTER TABLE orders ADD COLUMN destination VARCHAR",
        "ALTER TABLE orders ADD COLUMN estimated_finish_at DATETIME",
        "ALTER TABLE orders ADD COLUMN in_warehouse BOOLEAN DEFAULT 0",
    ]

    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass

        try:
            conn.execute(
                text("UPDATE orders SET status = 'Kesish' WHERE status IN ('Yangi', 'Upakofka')")
            )
            conn.commit()
        except Exception:
            pass
