import json
from pathlib import Path

from database import SessionLocal
from models import (
    Material,
    MaterialCategory,
    MesProductCategory,
    MesProductTemplate,
    MesProductPart,
)

SRC = Path("/var/www/velcore/real_master_export.json")
data = json.loads(SRC.read_text(encoding="utf-8"))

db = SessionLocal()

def clean(v):
    return "" if v is None else str(v).strip()


print("\n=== MATERIAL CATEGORIES ===")
for src in data["material_categories"]:
    code = clean(src.get("code"))
    name = clean(src.get("name"))

    matches = db.query(MaterialCategory).filter(
        (MaterialCategory.code == code) |
        (MaterialCategory.name == name)
    ).all()

    for dst in matches:
        print(
            "SRC", src.get("id"), code, name,
            "-> PROD", dst.id, dst.code, dst.name
        )


print("\n=== MATERIALS ===")
for src in data["materials"]:
    code = clean(src.get("code"))
    name = clean(src.get("name"))

    matches = db.query(Material).filter(
        (Material.code == code) |
        (Material.name == name)
    ).all()

    for dst in matches:
        print(
            "SRC", src.get("id"), code, name,
            "-> PROD", dst.id, dst.code, dst.name
        )


print("\n=== PRODUCT CATEGORIES ===")
for src in data["mes_product_categories"]:
    name = clean(src.get("name"))

    matches = db.query(MesProductCategory).filter(
        MesProductCategory.name == name
    ).all()

    for dst in matches:
        print(
            "SRC", src.get("id"), name,
            "-> PROD", dst.id, dst.name
        )


print("\n=== PRODUCT TEMPLATES ===")
for src in data["mes_product_templates"]:
    code = clean(src.get("code"))
    name = clean(src.get("name"))

    matches = db.query(MesProductTemplate).filter(
        (MesProductTemplate.code == code) |
        (MesProductTemplate.name == name)
    ).all()

    for dst in matches:
        print(
            "SRC", src.get("id"), code, name,
            "-> PROD", dst.id, dst.code, dst.name,
            "route=", dst.default_route_id
        )


print("\n=== PRODUCT PARTS ===")
for src in data["mes_product_parts"]:
    pn = clean(src.get("part_number"))
    name = clean(src.get("name"))

    matches = db.query(MesProductPart).filter(
        (MesProductPart.part_number == pn) |
        (MesProductPart.name == name)
    ).all()

    for dst in matches:
        print(
            "SRC", src.get("id"), pn, name,
            "-> PROD", dst.id, dst.part_number, dst.name,
            "material=", dst.material_id
        )

db.rollback()
db.close()

print("\nCOMPARE_OK — NO DATABASE WRITES")
