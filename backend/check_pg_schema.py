from database import engine
from sqlalchemy import inspect

tables = [
    "material_categories",
    "materials",
    "mes_product_categories",
    "mes_product_templates",
    "mes_product_parts",
]

inspector = inspect(engine)

for table in tables:
    print(f"\n### {table} ###")

    print("COLUMNS:")
    for col in inspector.get_columns(table):
        print(
            col["name"],
            str(col["type"]),
            "nullable=", col["nullable"],
            "default=", col.get("default"),
        )

    print("FOREIGN KEYS:")
    for fk in inspector.get_foreign_keys(table):
        print(
            fk.get("constrained_columns"),
            "->",
            fk.get("referred_table"),
            fk.get("referred_columns"),
        )
