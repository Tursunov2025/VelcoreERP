"""Additive professional material-master and physical length-lot migration."""

from sqlalchemy import inspect, text


MATERIAL_COLUMNS = {
    "material_type": "VARCHAR(32) NOT NULL DEFAULT 'CONSUMABLE'",
    "purchase_unit": "VARCHAR(24) NOT NULL DEFAULT 'dona'",
    "profile_type": "VARCHAR(32)",
    "steel_grade": "VARCHAR(80) NOT NULL DEFAULT ''",
    "description": "TEXT NOT NULL DEFAULT ''",
    "width_mm": "FLOAT",
    "height_mm": "FLOAT",
    "diameter_mm": "FLOAT",
    "thickness_mm": "FLOAT",
    "inner_radius_mm": "FLOAT",
    "length_mm": "FLOAT",
    "theoretical_weight_kg_per_m": "FLOAT",
    "density_kg_m3": "FLOAT",
    "default_kerf_mm": "FLOAT",
    "min_reusable_offcut_m": "FLOAT",
}

ISSUE_COLUMNS = {
    "document_number": "VARCHAR(100)", "operation_key": "VARCHAR(180)",
    "status": "VARCHAR(24) NOT NULL DEFAULT 'COMPLETED'", "project_id": "INTEGER",
    "project_line_id": "INTEGER", "job_id": "INTEGER", "operation_stage": "VARCHAR(80) NOT NULL DEFAULT 'LAZER'",
    "release_snapshot_id": "INTEGER", "material_reservation_id": "INTEGER",
    "source_material_bom_line_id": "INTEGER", "source_job_bom_line_id": "INTEGER",
    "planned_required_quantity": "FLOAT",
    "warehouse_name": "VARCHAR(120) NOT NULL DEFAULT ''", "responsible_employee": "VARCHAR(120) NOT NULL DEFAULT ''",
    "version": "INTEGER NOT NULL DEFAULT 1", "issued_at": "TIMESTAMP", "completed_at": "TIMESTAMP",
}
CUT_COLUMNS = {
    "project_id": "INTEGER", "project_line_id": "INTEGER", "release_snapshot_id": "INTEGER",
    "job_id": "INTEGER", "source_material_bom_line_id": "INTEGER", "source_job_bom_line_id": "INTEGER",
}

RECEIPT_COLUMNS = {
    "receipt_number": "VARCHAR(100)",
    "operation_key": "VARCHAR(180)",
    "confirm_key": "VARCHAR(180)",
    "reverse_key": "VARCHAR(180)",
    "status": "VARCHAR(24) NOT NULL DEFAULT 'CONFIRMED'",
    "supplier_name": "VARCHAR(180) NOT NULL DEFAULT ''",
    "supplier_invoice": "VARCHAR(180) NOT NULL DEFAULT ''",
    "warehouse_name": "VARCHAR(120) NOT NULL DEFAULT ''",
    "location_code": "VARCHAR(120) NOT NULL DEFAULT ''",
    "lot_number": "VARCHAR(120) NOT NULL DEFAULT ''",
    "purchase_unit": "VARCHAR(24) NOT NULL DEFAULT ''",
    "base_unit": "VARCHAR(24) NOT NULL DEFAULT ''",
    "price_basis": "VARCHAR(24) NOT NULL DEFAULT 'PER_UNIT'",
    "currency": "VARCHAR(8) NOT NULL DEFAULT 'UZS'",
    "total_pieces": "INTEGER NOT NULL DEFAULT 0",
    "total_weight_kg": "FLOAT",
    "total_amount": "FLOAT NOT NULL DEFAULT 0",
    "profile_rows_json": "TEXT NOT NULL DEFAULT '[]'",
    "stock_applied": "BOOLEAN NOT NULL DEFAULT TRUE",
    "version": "INTEGER NOT NULL DEFAULT 1",
    "received_at": "TIMESTAMP",
    "confirmed_at": "TIMESTAMP",
    "confirmed_by": "VARCHAR(100)",
    "reversed_at": "TIMESTAMP",
    "reversed_by": "VARCHAR(100)",
    "reversal_reason": "TEXT NOT NULL DEFAULT ''",
}

LENGTH_LOT_COLUMNS = {
    "receipt_document_id": "INTEGER REFERENCES material_receipts(id)",
    "pieces_received": "INTEGER NOT NULL DEFAULT 0",
    "meters_received": "FLOAT NOT NULL DEFAULT 0",
    "status": "VARCHAR(24) NOT NULL DEFAULT 'ACTIVE'",
    "supplier_name": "VARCHAR(180) NOT NULL DEFAULT ''",
    "supplier_invoice": "VARCHAR(180) NOT NULL DEFAULT ''",
}


def upgrade(engine) -> None:
    from models import MaterialCutOperation, MaterialIssuePiece, MaterialScrap, MaterialStockLengthLot, MaterialStockPiece

    MaterialStockLengthLot.__table__.create(bind=engine, checkfirst=True)
    for table in (MaterialStockPiece.__table__, MaterialIssuePiece.__table__, MaterialCutOperation.__table__, MaterialScrap.__table__):
        table.create(bind=engine, checkfirst=True)
    inspector = inspect(engine)
    if "materials" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("materials")}
    with engine.begin() as connection:
        for name, ddl in MATERIAL_COLUMNS.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE materials ADD COLUMN {name} {ddl}"))
        indexes = {index["name"] for index in inspect(connection).get_indexes("materials")}
        if "ix_materials_material_type" not in indexes:
            connection.execute(text("CREATE INDEX ix_materials_material_type ON materials (material_type)"))
        if "ix_materials_profile_type" not in indexes:
            connection.execute(text("CREATE INDEX ix_materials_profile_type ON materials (profile_type)"))

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as connection:
        if "material_receipts" in tables:
            existing = {column["name"] for column in inspect(connection).get_columns("material_receipts")}
            for name, ddl in RECEIPT_COLUMNS.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE material_receipts ADD COLUMN {name} {ddl}"))
            for name in ("receipt_number", "operation_key", "confirm_key", "reverse_key"):
                connection.execute(text(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS ux_material_receipts_{name} "
                    f"ON material_receipts ({name}) WHERE {name} IS NOT NULL"
                ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_material_receipts_status ON material_receipts (status)"
            ))
        if "material_stock_length_lots" in tables:
            existing = {column["name"] for column in inspect(connection).get_columns("material_stock_length_lots")}
            for name, ddl in LENGTH_LOT_COLUMNS.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE material_stock_length_lots ADD COLUMN {name} {ddl}"))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_material_length_lots_receipt_document "
                "ON material_stock_length_lots (receipt_document_id)"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_material_length_lots_status "
                "ON material_stock_length_lots (status)"
            ))
        if "material_issues" in tables:
            existing = {column["name"] for column in inspect(connection).get_columns("material_issues")}
            for name, ddl in ISSUE_COLUMNS.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE material_issues ADD COLUMN {name} {ddl}"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_material_issues_document_number ON material_issues(document_number) WHERE document_number IS NOT NULL"))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_material_issues_operation_key ON material_issues(operation_key) WHERE operation_key IS NOT NULL"))
        if "material_cut_operations" in tables:
            existing = {column["name"] for column in inspect(connection).get_columns("material_cut_operations")}
            for name, ddl in CUT_COLUMNS.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE material_cut_operations ADD COLUMN {name} {ddl}"))


def downgrade(engine) -> None:
    """Intentionally non-destructive; material identities and stock lots are business data."""
