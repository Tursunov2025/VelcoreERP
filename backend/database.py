import logging

import os

import shutil

import time

from pathlib import Path



from sqlalchemy import create_engine, event, text

from sqlalchemy.orm import declarative_base, sessionmaker



from config.paths import DATABASE_URL, DATABASE_URL_SOURCE, DB_PATH, ensure_data_directories

from config.production import mask_database_url



logger = logging.getLogger("azmus.database")

ensure_data_directories()



_SQLITE_TIMEOUT = int(os.getenv("SQLITE_TIMEOUT_SECONDS", "30"))



connect_args: dict = {}
engine_kwargs: dict = {"pool_pre_ping": True}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False,
        "timeout": _SQLITE_TIMEOUT,
    }
else:
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "10"))

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    **engine_kwargs,
)

logger.info(
    "SQLAlchemy engine created: url=%s source=%s",
    mask_database_url(DATABASE_URL),
    DATABASE_URL_SOURCE,
)


def verify_engine_connection() -> None:
    """Verify DB connectivity using the application engine (single source of truth)."""
    logger.info(
        "Verifying database connection: %s (source=%s)",
        mask_database_url(DATABASE_URL),
        DATABASE_URL_SOURCE,
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception(
            "Database connection failed — check DATABASE_URL in %s matches PostgreSQL password",
            DATABASE_URL_SOURCE,
        )
        raise





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

        """CREATE TABLE IF NOT EXISTS package_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL UNIQUE,
            label_code VARCHAR NOT NULL UNIQUE,
            qr_data TEXT DEFAULT '',
            barcode_data VARCHAR DEFAULT '',
            printed_at DATETIME,
            printer_name VARCHAR DEFAULT '',
            created_at DATETIME
        )""",

        """CREATE TABLE IF NOT EXISTS package_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL UNIQUE,
            warehouse_zone VARCHAR DEFAULT '',
            rack VARCHAR DEFAULT '',
            shelf VARCHAR DEFAULT '',
            updated_at DATETIME
        )""",

        "ALTER TABLE mes_dispatch_packages ADD COLUMN loaded_by VARCHAR",

        """CREATE TABLE IF NOT EXISTS print_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            package_id INTEGER NOT NULL,
            label_code VARCHAR NOT NULL,
            printer_name VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'pending',
            created_at DATETIME,
            printed_at DATETIME,
            error_message TEXT DEFAULT ''
        )""",

        """CREATE TABLE IF NOT EXISTS print_agent_heartbeats (
            printer_name VARCHAR PRIMARY KEY,
            last_seen_at DATETIME,
            hostname VARCHAR DEFAULT '',
            agent_version VARCHAR DEFAULT ''
        )""",

        """CREATE TABLE IF NOT EXISTS export_shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_number VARCHAR NOT NULL UNIQUE,
            order_id INTEGER,
            customer VARCHAR NOT NULL,
            country VARCHAR DEFAULT 'Kazakhstan',
            contract_number VARCHAR DEFAULT '',
            currency VARCHAR DEFAULT 'KZT',
            shipment_date DATETIME,
            status VARCHAR DEFAULT 'Draft',
            total_quantity FLOAT DEFAULT 0,
            total_weight FLOAT DEFAULT 0,
            total_amount FLOAT DEFAULT 0,
            notes TEXT DEFAULT '',
            created_by VARCHAR NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            sent_at DATETIME,
            delivered_at DATETIME
        )""",

        """CREATE TABLE IF NOT EXISTS export_shipment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            order_id INTEGER,
            product_name VARCHAR NOT NULL,
            description TEXT DEFAULT '',
            quantity FLOAT DEFAULT 1,
            unit VARCHAR DEFAULT 'pcs',
            weight_kg FLOAT DEFAULT 0,
            unit_price FLOAT DEFAULT 0,
            total_amount FLOAT DEFAULT 0,
            sort_order INTEGER DEFAULT 0
        )""",

        """CREATE TABLE IF NOT EXISTS export_shipment_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            document_type VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            url VARCHAR NOT NULL,
            filename VARCHAR DEFAULT '',
            content_type VARCHAR DEFAULT '',
            file_size INTEGER DEFAULT 0,
            llp_document_id INTEGER,
            generated_by VARCHAR NOT NULL,
            generated_at DATETIME
        )""",

        "CREATE INDEX IF NOT EXISTS ix_export_shipments_status ON export_shipments (status)",
        "CREATE INDEX IF NOT EXISTS ix_export_shipments_number ON export_shipments (shipment_number)",
        "CREATE INDEX IF NOT EXISTS ix_export_shipment_items_shipment ON export_shipment_items (shipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_export_shipment_documents_shipment ON export_shipment_documents (shipment_id)",

        # Phase 11B — ERP Modernization Suite (additive only)
        "ALTER TABLE orders ADD COLUMN currency VARCHAR DEFAULT 'UZS'",

        """CREATE TABLE IF NOT EXISTS currencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code VARCHAR NOT NULL UNIQUE,
            name VARCHAR NOT NULL,
            symbol VARCHAR DEFAULT '',
            is_base BOOLEAN DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME
        )""",

        """CREATE TABLE IF NOT EXISTS exchange_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency_code VARCHAR NOT NULL,
            rate_to_base FLOAT NOT NULL,
            rate_date DATETIME,
            created_by VARCHAR DEFAULT 'system',
            created_at DATETIME
        )""",

        """CREATE TABLE IF NOT EXISTS transports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_shipment_id INTEGER,
            vehicle VARCHAR NOT NULL,
            driver_name VARCHAR DEFAULT '',
            driver_phone VARCHAR DEFAULT '',
            shipment_weight_kg FLOAT DEFAULT 0,
            departure_date DATETIME,
            arrival_date DATETIME,
            status VARCHAR DEFAULT 'Draft',
            notes TEXT DEFAULT '',
            created_by VARCHAR NOT NULL,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY (export_shipment_id) REFERENCES export_shipments (id)
        )""",

        """CREATE TABLE IF NOT EXISTS transport_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transport_id INTEGER NOT NULL,
            status VARCHAR NOT NULL,
            comment TEXT DEFAULT '',
            created_by VARCHAR DEFAULT 'system',
            created_at DATETIME,
            FOREIGN KEY (transport_id) REFERENCES transports (id)
        )""",

        """CREATE TABLE IF NOT EXISTS customer_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer VARCHAR NOT NULL,
            order_id INTEGER,
            amount FLOAT NOT NULL,
            currency VARCHAR DEFAULT 'UZS',
            notes TEXT DEFAULT '',
            created_by VARCHAR NOT NULL,
            created_at DATETIME,
            FOREIGN KEY (order_id) REFERENCES orders (id)
        )""",

        "CREATE INDEX IF NOT EXISTS ix_exchange_rates_code_date ON exchange_rates (currency_code, rate_date)",
        "CREATE INDEX IF NOT EXISTS ix_transports_status ON transports (status)",
        "CREATE INDEX IF NOT EXISTS ix_transports_export_shipment ON transports (export_shipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_transport_events_transport ON transport_events (transport_id)",
        "CREATE INDEX IF NOT EXISTS ix_customer_payments_customer ON customer_payments (customer)",

        # Seed the four supported currencies (idempotent, never overwrites)
        "INSERT OR IGNORE INTO currencies (code, name, symbol, is_base, is_active, sort_order, created_at) "
        "VALUES ('UZS', 'Uzbek so''m', 'so''m', 1, 1, 0, CURRENT_TIMESTAMP)",
        "INSERT OR IGNORE INTO currencies (code, name, symbol, is_base, is_active, sort_order, created_at) "
        "VALUES ('KZT', 'Kazakhstani tenge', '₸', 0, 1, 1, CURRENT_TIMESTAMP)",
        "INSERT OR IGNORE INTO currencies (code, name, symbol, is_base, is_active, sort_order, created_at) "
        "VALUES ('USD', 'US Dollar', '$', 0, 1, 2, CURRENT_TIMESTAMP)",
        "INSERT OR IGNORE INTO currencies (code, name, symbol, is_base, is_active, sort_order, created_at) "
        "VALUES ('RUB', 'Russian ruble', '₽', 0, 1, 3, CURRENT_TIMESTAMP)",

        # Phase 12 — GPS Fleet Tracking (additive only)
        """CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number VARCHAR NOT NULL UNIQUE,
            model VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'active',
            created_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS drivers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name VARCHAR NOT NULL,
            phone VARCHAR DEFAULT '',
            telegram_username VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'active',
            created_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS gps_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL,
            driver_id INTEGER,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            speed REAL DEFAULT 0,
            battery_level REAL,
            recorded_at DATETIME,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
            FOREIGN KEY (driver_id) REFERENCES drivers (id)
        )""",
        """CREATE TABLE IF NOT EXISTS trip_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transport_id INTEGER,
            vehicle_id INTEGER NOT NULL,
            driver_id INTEGER,
            origin VARCHAR DEFAULT '',
            destination VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'Planned',
            started_at DATETIME,
            completed_at DATETIME,
            created_at DATETIME,
            FOREIGN KEY (transport_id) REFERENCES transports (id),
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
            FOREIGN KEY (driver_id) REFERENCES drivers (id)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_gps_locations_vehicle_recorded ON gps_locations (vehicle_id, recorded_at)",
        "CREATE INDEX IF NOT EXISTS ix_gps_locations_driver_recorded ON gps_locations (driver_id, recorded_at)",
        "CREATE INDEX IF NOT EXISTS ix_trip_routes_transport ON trip_routes (transport_id)",
        "CREATE INDEX IF NOT EXISTS ix_trip_routes_status ON trip_routes (status)",

        # GPS Monitoring — transport tasks
        """CREATE TABLE IF NOT EXISTS transport_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR NOT NULL,
            description TEXT DEFAULT '',
            vehicle_id INTEGER,
            driver_id INTEGER,
            transport_id INTEGER,
            origin VARCHAR DEFAULT '',
            destination VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'assigned',
            tracking_active INTEGER DEFAULT 0,
            started_at DATETIME,
            completed_at DATETIME,
            created_by VARCHAR DEFAULT '',
            created_at DATETIME,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
            FOREIGN KEY (driver_id) REFERENCES drivers (id),
            FOREIGN KEY (transport_id) REFERENCES transports (id)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_transport_tasks_status ON transport_tasks (status)",
        "CREATE INDEX IF NOT EXISTS ix_transport_tasks_vehicle ON transport_tasks (vehicle_id)",

        # LLP document delete — allow documents.id removal when linked from export shipments
        "ALTER TABLE export_shipment_documents DROP CONSTRAINT IF EXISTS export_shipment_documents_llp_document_id_fkey",
        """ALTER TABLE export_shipment_documents
            ADD CONSTRAINT export_shipment_documents_llp_document_id_fkey
            FOREIGN KEY (llp_document_id) REFERENCES documents(id) ON DELETE SET NULL""",

        # Phase 12.1 — GPS alert dedup state
        """CREATE TABLE IF NOT EXISTS logistics_finished_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code VARCHAR NOT NULL,
            product_name VARCHAR NOT NULL,
            order_number VARCHAR DEFAULT '',
            quantity FLOAT DEFAULT 1,
            warehouse_location VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'Tayyor',
            barcode VARCHAR UNIQUE,
            created_at DATETIME,
            updated_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS logistics_loading_shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_no VARCHAR NOT NULL UNIQUE,
            vehicle_id INTEGER,
            driver_id INTEGER,
            transport_id INTEGER,
            destination VARCHAR DEFAULT '',
            status VARCHAR DEFAULT 'planned',
            created_by VARCHAR DEFAULT '',
            created_at DATETIME,
            updated_at DATETIME,
            departed_at DATETIME,
            delivered_at DATETIME,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id),
            FOREIGN KEY (driver_id) REFERENCES drivers (id),
            FOREIGN KEY (transport_id) REFERENCES transports (id)
        )""",
        """CREATE TABLE IF NOT EXISTS logistics_loading_shipment_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shipment_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            qty FLOAT DEFAULT 1,
            loaded_at DATETIME,
            loaded_by VARCHAR DEFAULT '',
            FOREIGN KEY (shipment_id) REFERENCES logistics_loading_shipments (id),
            FOREIGN KEY (product_id) REFERENCES logistics_finished_products (id)
        )""",
        "CREATE INDEX IF NOT EXISTS ix_logistics_products_status ON logistics_finished_products (status)",
        "CREATE INDEX IF NOT EXISTS ix_logistics_products_barcode ON logistics_finished_products (barcode)",
        "CREATE INDEX IF NOT EXISTS ix_logistics_shipments_status ON logistics_loading_shipments (status)",

        "ALTER TABLE logistics_finished_products ADD COLUMN vehicle_id INTEGER REFERENCES vehicles (id)",
        "ALTER TABLE logistics_finished_products ADD COLUMN driver_id INTEGER REFERENCES drivers (id)",
        "UPDATE logistics_finished_products SET status = 'Available' WHERE status = 'Tayyor'",
        "UPDATE logistics_finished_products SET status = 'Reserved' WHERE status = 'Yuklanmoqda'",
        "UPDATE logistics_finished_products SET status = 'Loaded' WHERE status = 'Yuklandi'",
        "UPDATE logistics_finished_products SET status = 'Delivered' WHERE status = 'Yetkazildi'",

        "ALTER TABLE drivers ADD COLUMN driver_type VARCHAR DEFAULT 'internal'",
        "ALTER TABLE drivers ADD COLUMN user_username VARCHAR DEFAULT ''",
        "ALTER TABLE drivers ADD COLUMN default_vehicle_id INTEGER REFERENCES vehicles (id)",

        """CREATE TABLE IF NOT EXISTS gps_alert_state (
            vehicle_id INTEGER PRIMARY KEY,
            last_city VARCHAR DEFAULT '',
            last_country VARCHAR DEFAULT '',
            offline_alert_sent INTEGER DEFAULT 0,
            destination_alert_sent INTEGER DEFAULT 0,
            border_alert_sent INTEGER DEFAULT 0,
            updated_at DATETIME,
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id)
        )""",

        "ALTER TABLE audit_logs ADD COLUMN old_value TEXT DEFAULT ''",
        "ALTER TABLE audit_logs ADD COLUMN new_value TEXT DEFAULT ''",

        """CREATE TABLE IF NOT EXISTS ui_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key VARCHAR NOT NULL UNIQUE,
            value TEXT DEFAULT '',
            category VARCHAR DEFAULT 'general',
            updated_by VARCHAR DEFAULT '',
            updated_at DATETIME
        )""",
        """CREATE TABLE IF NOT EXISTS navigation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nav_key VARCHAR NOT NULL UNIQUE,
            label VARCHAR NOT NULL,
            icon VARCHAR DEFAULT '',
            emoji VARCHAR DEFAULT '',
            path VARCHAR DEFAULT '/',
            color VARCHAR DEFAULT '',
            sort_order INTEGER DEFAULT 0,
            parent_id INTEGER,
            visible INTEGER DEFAULT 1,
            hidden INTEGER DEFAULT 0,
            permissions_json TEXT DEFAULT '[]',
            module_key VARCHAR DEFAULT '',
            config_json TEXT DEFAULT '{}',
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY (parent_id) REFERENCES navigation_items (id)
        )""",
        """CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            perm_key VARCHAR NOT NULL UNIQUE,
            label VARCHAR NOT NULL,
            module VARCHAR DEFAULT '',
            description TEXT DEFAULT '',
            action VARCHAR DEFAULT ''
        )""",
        """CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_key VARCHAR NOT NULL UNIQUE,
            label VARCHAR NOT NULL,
            description TEXT DEFAULT '',
            is_system INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS role_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role_id INTEGER NOT NULL,
            permission_key VARCHAR NOT NULL,
            enabled INTEGER DEFAULT 1,
            FOREIGN KEY (role_id) REFERENCES roles (id),
            UNIQUE (role_id, permission_key)
        )""",
        """CREATE TABLE IF NOT EXISTS widgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            widget_key VARCHAR NOT NULL UNIQUE,
            title VARCHAR NOT NULL,
            widget_type VARCHAR DEFAULT 'stat',
            enabled INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            color VARCHAR DEFAULT '',
            layout_json TEXT DEFAULT '{}',
            config_json TEXT DEFAULT '{}'
        )""",
        """CREATE TABLE IF NOT EXISTS themes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR NOT NULL,
            is_active INTEGER DEFAULT 0,
            is_dark INTEGER DEFAULT 0,
            config_json TEXT DEFAULT '{}'
        )""",
        """CREATE TABLE IF NOT EXISTS module_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_key VARCHAR NOT NULL UNIQUE,
            enabled INTEGER DEFAULT 1,
            label VARCHAR NOT NULL,
            icon VARCHAR DEFAULT '',
            color VARCHAR DEFAULT '',
            url VARCHAR DEFAULT '/',
            permissions_json TEXT DEFAULT '[]',
            sort_order INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS feature_flags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flag_key VARCHAR NOT NULL UNIQUE,
            enabled INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            config_json TEXT DEFAULT '{}'
        )""",
        """CREATE TABLE IF NOT EXISTS ui_config_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label VARCHAR DEFAULT '',
            snapshot_json TEXT DEFAULT '{}',
            created_by VARCHAR DEFAULT '',
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


