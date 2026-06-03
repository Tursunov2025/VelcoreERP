import os

import shutil

import time

from pathlib import Path



from sqlalchemy import create_engine, event, text

from sqlalchemy.orm import declarative_base, sessionmaker



from config.paths import DATABASE_URL, DB_PATH, ensure_data_directories



ensure_data_directories()



_SQLITE_TIMEOUT = int(os.getenv("SQLITE_TIMEOUT_SECONDS", "30"))



connect_args: dict = {}

if DATABASE_URL.startswith("sqlite"):

    connect_args = {

        "check_same_thread": False,

        "timeout": _SQLITE_TIMEOUT,

    }



engine = create_engine(

    DATABASE_URL,

    connect_args=connect_args,

    pool_pre_ping=True,

)





@event.listens_for(engine, "connect")

def _configure_sqlite(dbapi_connection, _connection_record):

    if not DATABASE_URL.startswith("sqlite"):

        return

    cursor = dbapi_connection.cursor()

    cursor.execute("PRAGMA foreign_keys=ON")

    cursor.execute("PRAGMA journal_mode=WAL")

    cursor.execute(f"PRAGMA busy_timeout={_SQLITE_TIMEOUT * 1000}")

    cursor.close()





SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()





def replace_sqlite_database(db_path: Path, source_path: Path) -> None:

    """Replace the live SQLite file after closing all pooled ORM connections."""

    if not DATABASE_URL.startswith("sqlite"):

        raise RuntimeError("replace_sqlite_database is only supported for SQLite")

    if not source_path.is_file():

        raise FileNotFoundError(f"Source database not found: {source_path}")



    db_path = Path(db_path).resolve()

    source_path = Path(source_path).resolve()

    engine.dispose()



    db_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = db_path.with_suffix(f"{db_path.suffix}.incoming")

    if tmp_path.exists():

        tmp_path.unlink(missing_ok=True)

    shutil.copy2(source_path, tmp_path)



    last_error: OSError | None = None

    for attempt in range(15):

        try:

            os.replace(tmp_path, db_path)

            for suffix in ("-wal", "-shm"):

                sidecar = Path(f"{db_path}{suffix}")

                if sidecar.exists():

                    sidecar.unlink(missing_ok=True)

            return

        except OSError as exc:

            last_error = exc

            if attempt == 14:

                break

            time.sleep(0.2 * (attempt + 1))



    if tmp_path.exists():

        tmp_path.unlink(missing_ok=True)

    raise last_error or OSError(f"Could not replace SQLite database at {db_path}")





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

        "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1",

        "ALTER TABLE orders ADD COLUMN deleted_at DATETIME",

        "ALTER TABLE operator_activity ADD COLUMN login_at DATETIME",

        "ALTER TABLE shipment_groups ADD COLUMN deleted_at DATETIME",

        "ALTER TABLE users ADD COLUMN telegram_username VARCHAR",

        "ALTER TABLE users ADD COLUMN telegram_id VARCHAR",

        "ALTER TABLE users ADD COLUMN telegram_link_code VARCHAR",

        "ALTER TABLE users ADD COLUMN telegram_link_code_expires DATETIME",

        "ALTER TABLE users ADD COLUMN ui_language VARCHAR",

        "ALTER TABLE users ADD COLUMN ui_theme VARCHAR",

        "ALTER TABLE users ADD COLUMN ui_clock_format VARCHAR",

        "ALTER TABLE mes_product_templates ADD COLUMN length_mm FLOAT",

        "ALTER TABLE mes_product_templates ADD COLUMN width_mm FLOAT",

        "ALTER TABLE mes_product_templates ADD COLUMN height_mm FLOAT",

        "ALTER TABLE mes_product_templates ADD COLUMN weight_kg FLOAT",

        "ALTER TABLE mes_product_templates ADD COLUMN image_url VARCHAR",

        "ALTER TABLE mes_product_templates ADD COLUMN qr_prefix VARCHAR",

        "ALTER TABLE mes_bom_lines ADD COLUMN drawing_url VARCHAR",

        "ALTER TABLE mes_bom_lines ADD COLUMN is_active BOOLEAN DEFAULT 1",

        "ALTER TABLE mes_bom_lines ADD COLUMN deleted_at DATETIME",

        "ALTER TABLE mes_production_routes ADD COLUMN deleted_at DATETIME",

        "ALTER TABLE mes_route_steps ADD COLUMN department VARCHAR",

        "ALTER TABLE mes_route_steps ADD COLUMN responsible_role VARCHAR",

        "ALTER TABLE mes_route_steps ADD COLUMN required_parts_count INTEGER DEFAULT 0",

        "ALTER TABLE mes_route_steps ADD COLUMN completed_parts_count INTEGER DEFAULT 0",

        "ALTER TABLE mes_route_steps ADD COLUMN started_at DATETIME",

        "ALTER TABLE mes_route_steps ADD COLUMN accepted_at DATETIME",

        "ALTER TABLE mes_route_steps ADD COLUMN completed_at DATETIME",

        "ALTER TABLE mes_product_drawings ADD COLUMN is_active BOOLEAN DEFAULT 1",

        "ALTER TABLE mes_product_drawings ADD COLUMN deleted_at DATETIME",

        "ALTER TABLE mes_production_jobs ADD COLUMN paint_color_name VARCHAR DEFAULT ''",

        "ALTER TABLE mes_production_jobs ADD COLUMN paint_ral_code VARCHAR DEFAULT ''",

        "ALTER TABLE mes_production_jobs ADD COLUMN paint_type VARCHAR DEFAULT ''",

        "ALTER TABLE mes_production_jobs ADD COLUMN paint_batch_number VARCHAR DEFAULT ''",

        "ALTER TABLE mes_job_bom_lines ADD COLUMN painted_quantity FLOAT DEFAULT 0",

        "ALTER TABLE mes_job_route_steps ADD COLUMN drying_at DATETIME",

        "ALTER TABLE mes_job_bom_lines ADD COLUMN rework_quantity FLOAT DEFAULT 0",

        "ALTER TABLE mes_production_jobs ADD COLUMN package_type VARCHAR DEFAULT ''",

        "ALTER TABLE mes_production_jobs ADD COLUMN package_count INTEGER DEFAULT 0",

        "ALTER TABLE mes_production_jobs ADD COLUMN packaging_net_weight_kg FLOAT DEFAULT 0",

        "ALTER TABLE mes_production_jobs ADD COLUMN packaging_gross_weight_kg FLOAT DEFAULT 0",

        "ALTER TABLE mes_production_jobs ADD COLUMN packaging_notes TEXT DEFAULT ''",

        "ALTER TABLE mes_job_packages ADD COLUMN location_id INTEGER",

        "ALTER TABLE mes_job_packages ADD COLUMN received_at DATETIME",

        "ALTER TABLE mes_job_packages ADD COLUMN placed_at DATETIME",

        "ALTER TABLE materials ADD COLUMN code VARCHAR",

        "ALTER TABLE materials ADD COLUMN category_id INTEGER",

        "ALTER TABLE materials ADD COLUMN unit_cost FLOAT DEFAULT 0",

        "ALTER TABLE materials ADD COLUMN is_active BOOLEAN DEFAULT 1",

        "ALTER TABLE materials ADD COLUMN updated_at DATETIME",

        """CREATE TABLE IF NOT EXISTS mobile_app_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version_name VARCHAR NOT NULL,
            version_code INTEGER NOT NULL,
            apk_url VARCHAR NOT NULL DEFAULT '',
            release_notes TEXT DEFAULT '',
            force_update BOOLEAN DEFAULT 0,
            created_at DATETIME
        )""",

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


