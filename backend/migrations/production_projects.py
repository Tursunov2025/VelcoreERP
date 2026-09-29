"""Additive multi-product production-project migration.

New tables are created from SQLAlchemy metadata.  This unit adds nullable
linkage columns to existing MES tables for databases created before the
project aggregate existed.  It never removes data or columns.
"""

from sqlalchemy import inspect, text


MIGRATION_NAME = "2026_08_20_production_projects"

LINK_COLUMNS = {
    "project_production_operations": {
        "source_stage": "VARCHAR(40)",
        "destination_stage": "VARCHAR(40)",
        "reason_code": "VARCHAR(64)",
        "comment": "TEXT NOT NULL DEFAULT ''",
        "original_completed_at": "DATETIME",
        "reopened_at": "DATETIME",
        "reopened_by": "VARCHAR(100)",
    },
    "mes_production_jobs": {
        "project_id": "INTEGER",
        "project_line_id": "INTEGER",
        "project_release_snapshot_id": "INTEGER",
    },
    "mes_job_bom_lines": {
        "project_line_bom_snapshot_id": "INTEGER",
        "qc_accepted_quantity": "FLOAT NOT NULL DEFAULT 0",
        "qc_rejected_quantity": "FLOAT NOT NULL DEFAULT 0",
        "qc_rework_quantity": "FLOAT NOT NULL DEFAULT 0",
        "paint_accepted_quantity": "FLOAT NOT NULL DEFAULT 0",
        "paint_rejected_quantity": "FLOAT NOT NULL DEFAULT 0",
    },
    "mes_job_packages": {
        "quantity": "FLOAT DEFAULT 1",
        "project_id": "INTEGER",
        "project_line_id": "INTEGER",
        "project_release_snapshot_id": "INTEGER",
    },
    "mes_finished_goods_inventory": {
        "project_id": "INTEGER",
        "project_line_id": "INTEGER",
        "project_release_snapshot_id": "INTEGER",
    },
    "mes_warehouse_locations": {
        "segment_code": "VARCHAR(64) NOT NULL DEFAULT ''",
        "location_type": "VARCHAR(24) NOT NULL DEFAULT 'bin'",
        "parent_id": "INTEGER",
        "version": "INTEGER NOT NULL DEFAULT 1",
    },
    "mes_dispatches": {
        "project_id": "INTEGER",
        "destination_city": "VARCHAR(160) DEFAULT ''",
        "site_name": "VARCHAR(255) DEFAULT ''",
        "trip_id": "INTEGER",
    },
    "production_project_lines": {
        "delivered_quantity": "FLOAT NOT NULL DEFAULT 0",
        "accepted_quantity": "FLOAT NOT NULL DEFAULT 0",
        "damaged_quantity": "FLOAT NOT NULL DEFAULT 0",
        "missing_quantity": "FLOAT NOT NULL DEFAULT 0",
    },
    "mes_trips": {
        "evidence_policy": "VARCHAR(24) NOT NULL DEFAULT 'required'",
        "completeness_required": "BOOLEAN NOT NULL DEFAULT TRUE",
        "driver_user_id": "INTEGER",
        "planned_loading_at": "DATETIME",
        "delivery_deadline_at": "DATETIME",
    },
    "mes_vehicles": {
        "operational_state": "VARCHAR(16) NOT NULL DEFAULT 'AVAILABLE'",
        "internal_code": "VARCHAR(64) NOT NULL DEFAULT ''",
        "model": "VARCHAR(120) NOT NULL DEFAULT ''",
        "notes": "TEXT NOT NULL DEFAULT ''",
    },
    "mes_trip_tracking_sessions": {
        "last_contact_at": "DATETIME",
        "authorization_hash": "VARCHAR(64)",
        "authorization_expires_at": "DATETIME",
        "revoked_at": "DATETIME",
        "revoked_by": "VARCHAR(100)",
        "health_state": "VARCHAR(40) NOT NULL DEFAULT 'active'",
        "queued_point_count": "INTEGER NOT NULL DEFAULT 0",
        "latest_accuracy_m": "FLOAT",
        "latest_battery_level": "FLOAT",
        "device_id": "INTEGER",
    },
    "mes_gps_devices": {
        "protocol": "VARCHAR(32) NOT NULL DEFAULT 'custom_http'",
    },
    "mes_trip_locations": {
        "payload_hash": "VARCHAR(64) NOT NULL DEFAULT ''",
    },
    "mes_shipment_items": {
        "assignment_status": "VARCHAR(24) NOT NULL DEFAULT 'active'",
    },
}

INDEXES = (
    ("ix_mes_production_jobs_project_id", "mes_production_jobs", "project_id"),
    ("ix_mes_production_jobs_project_line_id", "mes_production_jobs", "project_line_id"),
    ("ix_mes_production_jobs_project_release_snapshot_id", "mes_production_jobs", "project_release_snapshot_id"),
    ("ix_mes_job_bom_lines_project_line_bom_snapshot_id", "mes_job_bom_lines", "project_line_bom_snapshot_id"),
    ("ix_mes_job_packages_project_id", "mes_job_packages", "project_id"),
    ("ix_mes_finished_goods_inventory_project_id", "mes_finished_goods_inventory", "project_id"),
    ("ix_mes_dispatches_project_id", "mes_dispatches", "project_id"),
    ("ix_mes_dispatches_trip_id", "mes_dispatches", "trip_id"),
    ("ix_mes_trips_driver_user_id", "mes_trips", "driver_user_id"),
    ("ix_mes_vehicles_operational_state", "mes_vehicles", "operational_state"),
    ("ix_mes_gps_devices_vehicle_id", "mes_gps_devices", "vehicle_id"),
    ("ix_mes_gps_devices_driver_user_id", "mes_gps_devices", "driver_user_id"),
    ("ix_mes_gps_devices_protocol", "mes_gps_devices", "protocol"),
    ("ix_mes_trip_tracking_sessions_device_id", "mes_trip_tracking_sessions", "device_id"),
    ("ix_mes_shipment_items_assignment_status", "mes_shipment_items", "assignment_status"),
    ("ix_mes_warehouse_locations_parent_id", "mes_warehouse_locations", "parent_id"),
    ("ix_mes_warehouse_locations_location_type", "mes_warehouse_locations", "location_type"),
)


def _column_ddl(dialect_name: str, column_type: str) -> str:
    """Translate the small portable column vocabulary to target-dialect DDL."""
    if dialect_name == "postgresql":
        return column_type.replace("DATETIME", "TIMESTAMP WITHOUT TIME ZONE")
    return column_type


def upgrade(engine) -> None:
    # Explicit, portable, additive creation for Checkpoint B. ``checkfirst``
    # makes this safe when startup metadata creation already created the tables.
    from models import (
        MesFinishedGoodsPlacement, MesLoadingPlanPlacement, MesShipmentItem,
        MesTrip, MesTripCommand, MesTripEvidence, MesTripLatestLocation, MesTripLocation,
        MesTripTrackingSession, MesVehicle, MesGpsDevice,
        ProductPassport, ProductPassportSequence, MesLoadCorrection,
        MesTripDocumentSnapshot, MesTripRoute, MesTripRouteStop,
    )

    for model in (
        MesFinishedGoodsPlacement, MesVehicle, MesTrip, MesShipmentItem,
        MesLoadingPlanPlacement, MesTripCommand, MesTripEvidence,
        MesTripTrackingSession, MesTripLocation, MesTripLatestLocation,
        MesGpsDevice, ProductPassport, ProductPassportSequence,
        MesLoadCorrection, MesTripDocumentSnapshot, MesTripRoute, MesTripRouteStop,
    ):
        model.__table__.create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        for table_name, columns in LINK_COLUMNS.items():
            if table_name not in table_names:
                continue
            existing = {column["name"] for column in inspect(connection).get_columns(table_name)}
            for column_name, column_type in columns.items():
                if column_name not in existing:
                    ddl = _column_ddl(engine.dialect.name, column_type)
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}"))
        existing_indexes = {
            index["name"]
            for _, table_name, _ in INDEXES
            if table_name in table_names
            for index in inspect(connection).get_indexes(table_name)
        }
        for index_name, table_name, column_name in INDEXES:
            if table_name in table_names and index_name not in existing_indexes:
                connection.execute(text(f"CREATE INDEX {index_name} ON {table_name} ({column_name})"))
        # Phase 3 permits deliberate vehicle unassignment in draft/planned state.
        # PostgreSQL can make this backward-compatible change in place. Fresh
        # SQLite fixtures receive the nullable definition from metadata.
        if engine.dialect.name == "postgresql" and "mes_trips" in table_names:
            connection.execute(text("ALTER TABLE mes_trips ALTER COLUMN vehicle_id DROP NOT NULL"))
        if engine.dialect.name == "postgresql" and "mes_vehicles" in table_names:
            connection.execute(text("UPDATE mes_vehicles SET operational_state = 'AVAILABLE' WHERE operational_state IS NULL"))
            connection.execute(text("ALTER TABLE mes_vehicles ALTER COLUMN operational_state SET DEFAULT 'AVAILABLE'"))
            connection.execute(text("ALTER TABLE mes_vehicles ALTER COLUMN operational_state SET NOT NULL"))
            connection.execute(text("""
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'ck_mes_vehicle_operational_state'
                          AND conrelid = 'mes_vehicles'::regclass
                    ) THEN
                        ALTER TABLE mes_vehicles ADD CONSTRAINT ck_mes_vehicle_operational_state
                        CHECK (operational_state IN ('AVAILABLE', 'SERVICE', 'INACTIVE'));
                    END IF;
                END $$
            """))


def downgrade(engine) -> None:
    """Refuse destructive downgrade when project data exists."""
    inspector = inspect(engine)
    if "production_projects" in inspector.get_table_names():
        with engine.connect() as connection:
            count = connection.execute(text("SELECT COUNT(*) FROM production_projects")).scalar_one()
        if count:
            raise RuntimeError("Refusing production-project downgrade while project data exists")
    raise RuntimeError("Destructive production-project downgrade requires an explicitly reviewed migration")
