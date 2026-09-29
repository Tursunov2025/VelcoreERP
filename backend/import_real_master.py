import json
from pathlib import Path

from sqlalchemy import text
from database import SessionLocal, engine

SRC = Path("/var/www/velcore/real_master_export.json")
data = json.loads(SRC.read_text(encoding="utf-8"))

db = SessionLocal()

try:
    conn = db.connection()

    # Existing production IDs by natural keys
    prod_material_categories = {
        row.code: row.id
        for row in db.execute(
            text("SELECT id, code FROM material_categories")
        ).mappings()
        if row["code"]
    }

    prod_materials = {
        row.code: row.id
        for row in db.execute(
            text("SELECT id, code FROM materials")
        ).mappings()
        if row["code"]
    }

    prod_product_categories = {
        row.name: row.id
        for row in db.execute(
            text("SELECT id, name FROM mes_product_categories")
        ).mappings()
        if row["name"]
    }

    prod_products = {
        row.code: row.id
        for row in db.execute(
            text("SELECT id, code FROM mes_product_templates")
        ).mappings()
        if row["code"]
    }

    prod_parts = {
        row.part_number: row.id
        for row in db.execute(
            text("SELECT id, part_number FROM mes_product_parts")
        ).mappings()
        if row["part_number"]
    }

    # Canonical production stages by name
    prod_stages = {
        row.name: row.id
        for row in db.execute(
            text("SELECT id, name FROM mes_production_stages")
        ).mappings()
    }

    category_id_map = {}
    material_id_map = {}
    product_category_id_map = {}
    product_id_map = {}
    part_id_map = {}
    route_id_map = {}

    inserted = {}

    # 1. Material categories
    count = 0
    for src in data["material_categories"]:
        old_id = src["id"]
        code = src.get("code")

        if code in prod_material_categories:
            category_id_map[old_id] = prod_material_categories[code]
            continue

        row = db.execute(
            text("""
                INSERT INTO material_categories
                (name, code, description, sort_order, is_active, created_at)
                VALUES
                (:name, :code, :description, :sort_order, :is_active, :created_at)
                RETURNING id
            """),
            src,
        ).scalar_one()

        category_id_map[old_id] = row
        prod_material_categories[code] = row
        count += 1

    inserted["material_categories"] = count

    # 2. Materials
    count = 0
    for src in data["materials"]:
        old_id = src["id"]
        code = src.get("code")

        if code and code in prod_materials:
            material_id_map[old_id] = prod_materials[code]
            continue

        payload = dict(src)
        payload.pop("id", None)
        payload["category_id"] = category_id_map.get(src.get("category_id"))

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO materials ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
            RETURNING id
        """

        new_id = db.execute(text(sql), payload).scalar_one()
        material_id_map[old_id] = new_id
        if code:
            prod_materials[code] = new_id
        count += 1

    inserted["materials"] = count

    # 3. Product categories
    count = 0
    for src in data["mes_product_categories"]:
        old_id = src["id"]
        name = src.get("name")

        if name in prod_product_categories:
            product_category_id_map[old_id] = prod_product_categories[name]
            continue

        payload = dict(src)
        payload.pop("id", None)
        payload["parent_id"] = None

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO mes_product_categories ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
            RETURNING id
        """

        new_id = db.execute(text(sql), payload).scalar_one()
        product_category_id_map[old_id] = new_id
        prod_product_categories[name] = new_id
        count += 1

    inserted["mes_product_categories"] = count

    # second pass for category parent_id
    for src in data["mes_product_categories"]:
        if src.get("parent_id"):
            db.execute(
                text("""
                    UPDATE mes_product_categories
                    SET parent_id = :parent_id
                    WHERE id = :id
                """),
                {
                    "id": product_category_id_map[src["id"]],
                    "parent_id": product_category_id_map.get(src["parent_id"]),
                },
            )

    # 4. Product templates
    count = 0
    pending_default_routes = []

    for src in data["mes_product_templates"]:
        old_id = src["id"]
        code = src.get("code")

        if code in prod_products:
            product_id_map[old_id] = prod_products[code]
            continue

        payload = dict(src)
        payload.pop("id", None)
        pending_default_routes.append(
            (old_id, src.get("default_route_id"))
        )
        payload["default_route_id"] = None
        payload["category_id"] = product_category_id_map.get(src.get("category_id"))

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO mes_product_templates ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
            RETURNING id
        """

        new_id = db.execute(text(sql), payload).scalar_one()
        product_id_map[old_id] = new_id
        prod_products[code] = new_id
        count += 1

    inserted["mes_product_templates"] = count

    # 5. Product parts
    count = 0
    for src in data["mes_product_parts"]:
        old_id = src["id"]
        pn = src.get("part_number")

        if pn in prod_parts:
            part_id_map[old_id] = prod_parts[pn]
            continue

        payload = dict(src)
        payload.pop("id", None)
        payload["material_id"] = material_id_map.get(src.get("material_id"))

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO mes_product_parts ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
            RETURNING id
        """

        new_id = db.execute(text(sql), payload).scalar_one()
        part_id_map[old_id] = new_id
        prod_parts[pn] = new_id
        count += 1

    inserted["mes_product_parts"] = count

    # 6. Active production routes only
    active_route_ids = set()

    for src in data["mes_production_routes"]:
        if not src.get("is_active"):
            continue
        if src.get("deleted_at") is not None:
            continue
        active_route_ids.add(src["id"])

    count = 0
    for src in data["mes_production_routes"]:
        if src["id"] not in active_route_ids:
            continue

        payload = dict(src)
        old_id = payload.pop("id")
        payload["template_id"] = product_id_map[src["template_id"]]

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO mes_production_routes ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
            RETURNING id
        """

        new_id = db.execute(text(sql), payload).scalar_one()
        route_id_map[old_id] = new_id
        count += 1

    inserted["mes_production_routes"] = count

    # 7. Route steps
    count = 0
    local_stage_names = {
        1: "Lazer",
        4: "Svarshik",
        6: "Kraska",
        8: "Nazorat",
        9: "Upakovka",
        10: "Sklad",
        11: "Yuklash",
    }

    for src in data["mes_route_steps"]:
        if src["route_id"] not in route_id_map:
            continue

        stage_name = local_stage_names.get(src["stage_id"])
        if not stage_name:
            continue

        new_stage_id = prod_stages.get(stage_name)
        if not new_stage_id:
            raise RuntimeError(f"Missing production stage: {stage_name}")

        payload = dict(src)
        payload.pop("id", None)
        payload["route_id"] = route_id_map[src["route_id"]]
        payload["stage_id"] = new_stage_id

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO mes_route_steps ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
            RETURNING id
        """

        db.execute(text(sql), payload)
        count += 1

    inserted["mes_route_steps"] = count

    # 8. Restore default_route_id
    for old_product_id, old_route_id in pending_default_routes:
        if old_route_id in route_id_map:
            db.execute(
                text("""
                    UPDATE mes_product_templates
                    SET default_route_id = :route_id
                    WHERE id = :product_id
                """),
                {
                    "product_id": product_id_map[old_product_id],
                    "route_id": route_id_map[old_route_id],
                },
            )

    # 9. MES BOM
    count = 0
    for src in data["mes_bom_lines"]:
        if src.get("deleted_at") is not None:
            continue

        payload = dict(src)
        payload.pop("id", None)
        payload["template_id"] = product_id_map[src["template_id"]]
        payload["part_id"] = part_id_map[src["part_id"]]

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO mes_bom_lines ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
        """

        db.execute(text(sql), payload)
        count += 1

    inserted["mes_bom_lines"] = count

    # 10. Material BOM
    count = 0
    for src in data["material_bom_lines"]:
        payload = dict(src)
        payload.pop("id", None)
        payload["part_id"] = part_id_map[src["part_id"]]
        payload["material_id"] = material_id_map[src["material_id"]]

        cols = list(payload.keys())
        sql = f"""
            INSERT INTO material_bom_lines ({', '.join(cols)})
            VALUES ({', '.join(':' + c for c in cols)})
        """

        db.execute(text(sql), payload)
        count += 1

    inserted["material_bom_lines"] = count

    print("\nIMPORT SUMMARY")
    for k, v in inserted.items():
        print(k, v)

    print("\nABOUT TO COMMIT")
    db.commit()
    print("IMPORT_COMMIT_OK")

except Exception:
    db.rollback()
    print("IMPORT_ROLLBACK")
    raise

finally:
    db.close()
