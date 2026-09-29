from database import engine
from sqlalchemy import text

tables = [
    ("material_categories", ["id", "code", "name"]),
    ("materials", ["id", "code", "name", "material_type"]),
    ("mes_product_categories", ["id", "name"]),
    ("mes_product_templates", ["id", "code", "name"]),
    ("mes_product_parts", ["id", "part_number", "name", "material_id"]),
]

with engine.connect() as conn:
    for table, columns in tables:
        print(f"\n### {table} ###")
        sql = f"SELECT {', '.join(columns)} FROM {table} ORDER BY id"
        for row in conn.execute(text(sql)):
            print(tuple(row))
