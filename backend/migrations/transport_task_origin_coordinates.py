"""Add optional origin coordinates to transport_tasks."""

from sqlalchemy import text


def upgrade(engine):
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(
                text(
                    """
                    ALTER TABLE transport_tasks
                    ADD COLUMN IF NOT EXISTS origin_latitude DOUBLE PRECISION
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE transport_tasks
                    ADD COLUMN IF NOT EXISTS origin_longitude DOUBLE PRECISION
                    """
                )
            )
        else:
            existing = {
                row[1]
                for row in conn.execute(text("PRAGMA table_info(transport_tasks)"))
            }

            if "origin_latitude" not in existing:
                conn.execute(
                    text(
                        "ALTER TABLE transport_tasks "
                        "ADD COLUMN origin_latitude REAL"
                    )
                )

            if "origin_longitude" not in existing:
                conn.execute(
                    text(
                        "ALTER TABLE transport_tasks "
                        "ADD COLUMN origin_longitude REAL"
                    )
                )
