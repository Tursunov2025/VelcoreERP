"""Add direct Material support to MES Yig‘ish lines."""

from sqlalchemy import inspect, text


def _has_column(inspector, table_name, column_name):
    return any(c["name"] == column_name for c in inspector.get_columns(table_name))


def _has_constraint(inspector, table_name, name):
    return any(c.get("name") == name for c in inspector.get_unique_constraints(table_name))


def _has_fk(inspector, table_name, name):
    return any(c.get("name") == name for c in inspector.get_foreign_keys(table_name))


def upgrade_yigish_materials(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if "mes_yigish_lines" not in tables or "mes_job_yigish_lines" not in tables:
        print("YIGISH MATERIAL MIGRATION SKIPPED: tables missing")
        return

    if engine.dialect.name != "postgresql":
        print(f"YIGISH MATERIAL MIGRATION SKIPPED: {engine.dialect.name}")
        return

    with engine.begin() as conn:
        if not _has_column(inspector, "mes_yigish_lines", "material_id"):
            conn.execute(text(
                "ALTER TABLE mes_yigish_lines ADD COLUMN material_id INTEGER NULL"
            ))
            print("Added mes_yigish_lines.material_id")

        inspector = inspect(engine)

        if not _has_column(inspector, "mes_job_yigish_lines", "material_id"):
            conn.execute(text(
                "ALTER TABLE mes_job_yigish_lines ADD COLUMN material_id INTEGER NULL"
            ))
            print("Added mes_job_yigish_lines.material_id")

        conn.execute(text(
            "ALTER TABLE mes_yigish_lines ALTER COLUMN part_id DROP NOT NULL"
        ))
        conn.execute(text(
            "ALTER TABLE mes_job_yigish_lines ALTER COLUMN part_id DROP NOT NULL"
        ))

        inspector = inspect(engine)

        if not _has_fk(
            inspector,
            "mes_yigish_lines",
            "mes_yigish_lines_material_id_fkey",
        ):
            conn.execute(text(
                "ALTER TABLE mes_yigish_lines "
                "ADD CONSTRAINT mes_yigish_lines_material_id_fkey "
                "FOREIGN KEY (material_id) REFERENCES materials(id)"
            ))

        inspector = inspect(engine)

        if not _has_fk(
            inspector,
            "mes_job_yigish_lines",
            "mes_job_yigish_lines_material_id_fkey",
        ):
            conn.execute(text(
                "ALTER TABLE mes_job_yigish_lines "
                "ADD CONSTRAINT mes_job_yigish_lines_material_id_fkey "
                "FOREIGN KEY (material_id) REFERENCES materials(id)"
            ))

        inspector = inspect(engine)

        if not _has_constraint(
            inspector,
            "mes_yigish_lines",
            "uq_mes_yigish_template_material",
        ):
            conn.execute(text(
                "ALTER TABLE mes_yigish_lines "
                "ADD CONSTRAINT uq_mes_yigish_template_material "
                "UNIQUE (template_id, material_id)"
            ))

        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mes_yigish_lines_material_id "
            "ON mes_yigish_lines (material_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_mes_job_yigish_lines_material_id "
            "ON mes_job_yigish_lines (material_id)"
        ))

    print("YIGISH MATERIAL MIGRATION COMPLETED")
