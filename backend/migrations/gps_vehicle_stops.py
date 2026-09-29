"""Add persistent GPS vehicle stop history."""

from sqlalchemy import text


def upgrade(engine):
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS gps_vehicle_stops (
                    id BIGSERIAL PRIMARY KEY,
                    vehicle_id INTEGER NOT NULL,
                    start_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    end_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    latitude DOUBLE PRECISION NOT NULL,
                    longitude DOUBLE PRECISION NOT NULL,
                    address TEXT DEFAULT '',
                    road TEXT DEFAULT '',
                    house_number TEXT DEFAULT '',
                    city TEXT DEFAULT '',
                    state TEXT DEFAULT '',
                    country TEXT DEFAULT '',
                    point_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS
                ix_gps_vehicle_stops_vehicle_start
                ON gps_vehicle_stops (vehicle_id, start_at)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS
                ix_gps_vehicle_stops_vehicle_end
                ON gps_vehicle_stops (vehicle_id, end_at)
            """))

            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                ux_gps_vehicle_stops_vehicle_start_end
                ON gps_vehicle_stops (vehicle_id, start_at, end_at)
            """))

        else:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS gps_vehicle_stops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL,
                    start_at DATETIME NOT NULL,
                    end_at DATETIME NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    address TEXT DEFAULT '',
                    road TEXT DEFAULT '',
                    house_number TEXT DEFAULT '',
                    city TEXT DEFAULT '',
                    state TEXT DEFAULT '',
                    country TEXT DEFAULT '',
                    point_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS
                ix_gps_vehicle_stops_vehicle_start
                ON gps_vehicle_stops (vehicle_id, start_at)
            """))

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS
                ix_gps_vehicle_stops_vehicle_end
                ON gps_vehicle_stops (vehicle_id, end_at)
            """))

            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                ux_gps_vehicle_stops_vehicle_start_end
                ON gps_vehicle_stops (vehicle_id, start_at, end_at)
            """))
