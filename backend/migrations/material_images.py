"""Add image URL support to materials."""

from sqlalchemy import inspect, text


def upgrade_material_images(engine):
    inspector = inspect(engine)

    if "materials" not in inspector.get_table_names():
        print("MATERIAL IMAGE MIGRATION SKIPPED: materials table missing")
        return

    if engine.dialect.name != "postgresql":
        print(f"MATERIAL IMAGE MIGRATION SKIPPED: {engine.dialect.name}")
        return

    has_column = any(
        col["name"] == "image_url"
        for col in inspector.get_columns("materials")
    )

    if not has_column:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE materials ADD COLUMN image_url VARCHAR(500) NULL")
            )
        print("Added materials.image_url")
    else:
        print("materials.image_url already exists")

    print("MATERIAL IMAGE MIGRATION COMPLETED")
