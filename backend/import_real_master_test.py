import json
from pathlib import Path

from sqlalchemy import inspect, text

from database import SessionLocal, engine


# ============================================================
# SOURCE
# ============================================================

SRC = Path("/var/www/velcore/real_master_export.json")

data = json.loads(
    SRC.read_text(encoding="utf-8")
)


# ============================================================
# EXCLUDED TEST DATA
# ============================================================

EXCLUDED_PRODUCT_CODES = {
    "BOM-11",
    "DR-A5",
}

EXCLUDED_MATERIAL_CATEGORY_CODES = {
    "TMC",
}

EXCLUDED_MATERIAL_CATEGORY_NAMES = {
    "TestMatCat",
}


# ============================================================
# SQLITE -> POSTGRES NORMALIZATION
# ============================================================

BOOL_FIELDS = {
    "is_active",
    "is_default",
    "is_required",
}

for rows in data.values():
    for row in rows:
        for field in BOOL_FIELDS:
            if field in row and row[field] is not None:
                row[field] = bool(row[field])


# ============================================================
# EXCLUSION MAPS
# ============================================================

excluded_product_ids = set()

excluded_material_category_ids = {
    row["id"]
    for row in data["material_categories"]
    if (
        row.get("code") in EXCLUDED_MATERIAL_CATEGORY_CODES
        or row.get("name") in EXCLUDED_MATERIAL_CATEGORY_NAMES
    )
}

excluded_material_ids = {
    row["id"]
    for row in data["materials"]
    if row.get("category_id") in excluded_material_category_ids
}


# ============================================================
# TARGET TABLE COLUMNS
# ============================================================

inspector = inspect(engine)

TARGET_COLUMNS = {
    table: {
        column["name"]
        for column in inspector.get_columns(table)
    }
    for table in [
        "material_categories",
        "materials",
        "mes_product_categories",
        "mes_product_templates",
        "mes_product_parts",
        "mes_production_routes",
        "mes_route_steps",
        "mes_bom_lines",
        "material_bom_lines",
    ]
}


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def filtered_payload(table, row):
    """
    Remove SQLite-only / unsupported columns and ID.
    """
    allowed = TARGET_COLUMNS[table]

    return {
        key: value
        for key, value in row.items()
        if key != "id" and key in allowed
    }


def insert_returning_id(db, table, payload):
    columns = list(payload.keys())

    sql = f"""
        INSERT INTO {table}
        ({", ".join(columns)})
        VALUES ({", ".join(":" + c for c in columns)})
        RETURNING id
    """

    return db.execute(
        text(sql),
        payload,
    ).scalar_one()


# ============================================================
# DATABASE SESSION
# ============================================================

db = SessionLocal()

try:

    # ========================================================
    # CURRENT PRODUCTION NATURAL KEYS
    # ========================================================

    prod_material_categories_by_code = {}
    prod_material_categories_by_name = {}

    for row in db.execute(
        text("""
            SELECT id, code, name
            FROM material_categories
        """)
    ).mappings():

        if row["code"]:
            prod_material_categories_by_code[
                clean(row["code"])
            ] = row["id"]

        if row["name"]:
            prod_material_categories_by_name[
                clean(row["name"])
            ] = row["id"]


    prod_materials_by_code = {}
    prod_materials_by_name = {}

    for row in db.execute(
        text("""
            SELECT id, code, name
            FROM materials
        """)
    ).mappings():

        if row["code"]:
            prod_materials_by_code[
                clean(row["code"])
            ] = row["id"]

        if row["name"]:
            prod_materials_by_name[
                clean(row["name"])
            ] = row["id"]


    prod_product_categories_by_name = {}

    for row in db.execute(
        text("""
            SELECT id, name
            FROM mes_product_categories
        """)
    ).mappings():

        if row["name"]:
            prod_product_categories_by_name[
                clean(row["name"])
            ] = row["id"]


    prod_products_by_code = {}

    for row in db.execute(
        text("""
            SELECT id, code
            FROM mes_product_templates
        """)
    ).mappings():

        if row["code"]:
            prod_products_by_code[
                clean(row["code"])
            ] = row["id"]


    prod_parts_by_number = {}

    for row in db.execute(
        text("""
            SELECT id, part_number
            FROM mes_product_parts
        """)
    ).mappings():

        if row["part_number"]:
            prod_parts_by_number[
                clean(row["part_number"])
            ] = row["id"]


    # ========================================================
    # CANONICAL PRODUCTION STAGES
    # ========================================================

    prod_stages = {
        clean(row["name"]): row["id"]
        for row in db.execute(
            text("""
                SELECT id, name
                FROM mes_production_stages
            """)
        ).mappings()
    }

    local_stage_names = {
        1: "Lazer",
        4: "Svarshik",
        6: "Kraska",
        8: "Nazorat",
        9: "Upakovka",
        10: "Sklad",
        11: "Yuklash",
    }


    # ========================================================
    # ID MAPS
    # ========================================================

    category_id_map = {}
    material_id_map = {}
    product_category_id_map = {}
    product_id_map = {}
    part_id_map = {}
    route_id_map = {}

    inserted = {}
    matched = {}


    # ========================================================
    # 1. MATERIAL CATEGORIES
    # ========================================================

    insert_count = 0
    match_count = 0

    for src in data["material_categories"]:

        old_id = src["id"]

        if old_id in excluded_material_category_ids:
            continue

        code = clean(src.get("code"))
        name = clean(src.get("name"))

        existing_id = None

        if code:
            existing_id = (
                prod_material_categories_by_code.get(code)
            )

        if existing_id is None and name:
            existing_id = (
                prod_material_categories_by_name.get(name)
            )

        if existing_id is not None:
            category_id_map[old_id] = existing_id
            match_count += 1
            continue

        payload = filtered_payload(
            "material_categories",
            src,
        )

        new_id = insert_returning_id(
            db,
            "material_categories",
            payload,
        )

        category_id_map[old_id] = new_id

        if code:
            prod_material_categories_by_code[
                code
            ] = new_id

        if name:
            prod_material_categories_by_name[
                name
            ] = new_id

        insert_count += 1

    inserted["material_categories"] = insert_count
    matched["material_categories"] = match_count


    # ========================================================
    # 2. MATERIALS
    # ========================================================

    insert_count = 0
    match_count = 0

    for src in data["materials"]:

        old_id = src["id"]

        if old_id in excluded_material_ids:
            continue

        code = clean(src.get("code"))
        name = clean(src.get("name"))

        existing_id = None

        if code:
            existing_id = prod_materials_by_code.get(code)

        if existing_id is None and name:
            existing_id = prod_materials_by_name.get(name)

        if existing_id is not None:
            material_id_map[old_id] = existing_id
            match_count += 1
            continue

        payload = filtered_payload(
            "materials",
            src,
        )

        old_category_id = src.get("category_id")

        payload["category_id"] = (
            category_id_map.get(old_category_id)
            if old_category_id is not None
            else None
        )

        new_id = insert_returning_id(
            db,
            "materials",
            payload,
        )

        material_id_map[old_id] = new_id

        if code:
            prod_materials_by_code[code] = new_id

        if name:
            prod_materials_by_name[name] = new_id

        insert_count += 1

    inserted["materials"] = insert_count
    matched["materials"] = match_count


    # ========================================================
    # 3. PRODUCT CATEGORIES
    # ========================================================

    insert_count = 0
    match_count = 0

    for src in data["mes_product_categories"]:

        old_id = src["id"]
        name = clean(src.get("name"))

        existing_id = (
            prod_product_categories_by_name.get(name)
            if name
            else None
        )

        if existing_id is not None:
            product_category_id_map[old_id] = existing_id
            match_count += 1
            continue

        payload = filtered_payload(
            "mes_product_categories",
            src,
        )

        # Parent mapping second passda qilinadi
        payload["parent_id"] = None

        new_id = insert_returning_id(
            db,
            "mes_product_categories",
            payload,
        )

        product_category_id_map[old_id] = new_id

        if name:
            prod_product_categories_by_name[
                name
            ] = new_id

        insert_count += 1

    inserted["mes_product_categories"] = insert_count
    matched["mes_product_categories"] = match_count


    # ========================================================
    # PRODUCT CATEGORY PARENT SECOND PASS
    # ========================================================

    for src in data["mes_product_categories"]:

        old_parent_id = src.get("parent_id")

        if not old_parent_id:
            continue

        current_id = product_category_id_map.get(
            src["id"]
        )

        mapped_parent_id = product_category_id_map.get(
            old_parent_id
        )

        if current_id and mapped_parent_id:

            db.execute(
                text("""
                    UPDATE mes_product_categories
                    SET parent_id = :parent_id
                    WHERE id = :id
                      AND parent_id IS NULL
                """),
                {
                    "id": current_id,
                    "parent_id": mapped_parent_id,
                },
            )


    # ========================================================
    # 4. PRODUCT TEMPLATES
    # ========================================================

    insert_count = 0
    match_count = 0

    inserted_product_ids = set()

    pending_default_routes = []

    for src in data["mes_product_templates"]:

        old_id = src["id"]

        if old_id in excluded_product_ids:
            continue

        code = clean(src.get("code"))

        existing_id = (
            prod_products_by_code.get(code)
            if code
            else None
        )

        if existing_id is not None:

            product_id_map[old_id] = existing_id
            match_count += 1

            continue

        payload = filtered_payload(
            "mes_product_templates",
            src,
        )

        pending_default_routes.append(
            (
                old_id,
                src.get("default_route_id"),
            )
        )

        payload["default_route_id"] = None

        old_category_id = src.get("category_id")

        payload["category_id"] = (
            product_category_id_map.get(
                old_category_id
            )
            if old_category_id is not None
            else None
        )

        new_id = insert_returning_id(
            db,
            "mes_product_templates",
            payload,
        )

        product_id_map[old_id] = new_id
        inserted_product_ids.add(old_id)

        if code:
            prod_products_by_code[code] = new_id

        insert_count += 1

    inserted["mes_product_templates"] = insert_count
    matched["mes_product_templates"] = match_count


    # ========================================================
    # 5. PRODUCT PARTS
    # ========================================================

    insert_count = 0
    match_count = 0

    for src in data["mes_product_parts"]:

        old_id = src["id"]
        part_number = clean(src.get("part_number"))

        existing_id = (
            prod_parts_by_number.get(part_number)
            if part_number
            else None
        )

        if existing_id is not None:

            part_id_map[old_id] = existing_id
            match_count += 1

            continue

        payload = filtered_payload(
            "mes_product_parts",
            src,
        )

        old_material_id = src.get("material_id")

        if old_material_id in excluded_material_ids:
            payload["material_id"] = None
        else:
            payload["material_id"] = (
                material_id_map.get(old_material_id)
                if old_material_id is not None
                else None
            )

        new_id = insert_returning_id(
            db,
            "mes_product_parts",
            payload,
        )

        part_id_map[old_id] = new_id

        if part_number:
            prod_parts_by_number[
                part_number
            ] = new_id

        insert_count += 1

    inserted["mes_product_parts"] = insert_count
    matched["mes_product_parts"] = match_count


    # ========================================================
    # 6. ACTIVE PRODUCTION ROUTES
    # ========================================================

    active_routes = []

    for src in data["mes_production_routes"]:

        if src["template_id"] in excluded_product_ids:
            continue

        if not src.get("is_active"):
            continue

        if src.get("deleted_at") is not None:
            continue

        active_routes.append(src)


    insert_count = 0
    match_count = 0

    for src in active_routes:

        old_route_id = src["id"]

        target_template_id = product_id_map[
            src["template_id"]
        ]

        route_name = clean(src.get("name"))
        version = src.get("version")

        existing = db.execute(
            text("""
                SELECT id
                FROM mes_production_routes
                WHERE template_id = :template_id
                  AND name = :name
                  AND (
                        version = :version
                        OR (
                            version IS NULL
                            AND :version IS NULL
                        )
                  )
                  AND deleted_at IS NULL
                ORDER BY id
                LIMIT 1
            """),
            {
                "template_id": target_template_id,
                "name": route_name,
                "version": version,
            },
        ).scalar()

        if existing is not None:

            route_id_map[old_route_id] = existing
            match_count += 1
            continue

        payload = filtered_payload(
            "mes_production_routes",
            src,
        )

        payload["template_id"] = (
            target_template_id
        )

        new_id = insert_returning_id(
            db,
            "mes_production_routes",
            payload,
        )

        route_id_map[old_route_id] = new_id
        insert_count += 1

    inserted["mes_production_routes"] = insert_count
    matched["mes_production_routes"] = match_count


    # ========================================================
    # 7. ROUTE STEPS
    # ========================================================

    insert_count = 0
    match_count = 0
    skipped_count = 0

    for src in data["mes_route_steps"]:

        old_route_id = src["route_id"]

        if old_route_id not in route_id_map:
            continue

        stage_name = local_stage_names.get(
            src["stage_id"]
        )

        # Custom/Test stage skip
        if not stage_name:
            skipped_count += 1
            continue

        target_stage_id = prod_stages.get(
            stage_name
        )

        if target_stage_id is None:
            raise RuntimeError(
                f"Missing production stage: {stage_name}"
            )

        target_route_id = route_id_map[
            old_route_id
        ]

        existing = db.execute(
            text("""
                SELECT id
                FROM mes_route_steps
                WHERE route_id = :route_id
                  AND stage_id = :stage_id
                  AND step_order = :step_order
                ORDER BY id
                LIMIT 1
            """),
            {
                "route_id": target_route_id,
                "stage_id": target_stage_id,
                "step_order": src["step_order"],
            },
        ).scalar()

        if existing is not None:
            match_count += 1
            continue

        payload = filtered_payload(
            "mes_route_steps",
            src,
        )

        payload["route_id"] = target_route_id
        payload["stage_id"] = target_stage_id

        insert_returning_id(
            db,
            "mes_route_steps",
            payload,
        )

        insert_count += 1

    inserted["mes_route_steps"] = insert_count
    matched["mes_route_steps"] = match_count
    inserted["mes_route_steps_skipped"] = skipped_count


    # ========================================================
    # 8. RESTORE DEFAULT ROUTES FOR NEW PRODUCTS
    # ========================================================

    for old_product_id, old_route_id in pending_default_routes:

        new_product_id = product_id_map.get(
            old_product_id
        )

        new_route_id = route_id_map.get(
            old_route_id
        )

        if new_product_id and new_route_id:

            db.execute(
                text("""
                    UPDATE mes_product_templates
                    SET default_route_id = :route_id
                    WHERE id = :product_id
                """),
                {
                    "product_id": new_product_id,
                    "route_id": new_route_id,
                },
            )


    # ========================================================
    # 9. MES BOM LINES
    # ========================================================

    insert_count = 0
    match_count = 0
    skipped_count = 0

    for src in data["mes_bom_lines"]:

        if src["template_id"] in excluded_product_ids:
            skipped_count += 1
            continue

        if src.get("deleted_at") is not None:
            continue

        target_template_id = product_id_map.get(
            src["template_id"]
        )

        target_part_id = part_id_map.get(
            src["part_id"]
        )

        if target_template_id is None:
            raise RuntimeError(
                f"Missing product map: {src['template_id']}"
            )

        if target_part_id is None:
            raise RuntimeError(
                f"Missing part map: {src['part_id']}"
            )

        existing = db.execute(
            text("""
                SELECT id
                FROM mes_bom_lines
                WHERE template_id = :template_id
                  AND part_id = :part_id
                  AND COALESCE(sort_order, -1)
                      = COALESCE(:sort_order, -1)
                  AND deleted_at IS NULL
                ORDER BY id
                LIMIT 1
            """),
            {
                "template_id": target_template_id,
                "part_id": target_part_id,
                "sort_order": src.get("sort_order"),
            },
        ).scalar()

        if existing is not None:
            match_count += 1
            continue

        payload = filtered_payload(
            "mes_bom_lines",
            src,
        )

        payload["template_id"] = (
            target_template_id
        )

        payload["part_id"] = target_part_id

        insert_returning_id(
            db,
            "mes_bom_lines",
            payload,
        )

        insert_count += 1

    inserted["mes_bom_lines"] = insert_count
    matched["mes_bom_lines"] = match_count
    inserted["mes_bom_lines_skipped"] = skipped_count


    # ========================================================
    # 10. MATERIAL BOM LINES
    # ========================================================

    insert_count = 0
    match_count = 0
    skipped_count = 0

    for src in data["material_bom_lines"]:

        old_material_id = src["material_id"]

        if old_material_id in excluded_material_ids:
            skipped_count += 1
            continue

        target_part_id = part_id_map.get(
            src["part_id"]
        )

        target_material_id = material_id_map.get(
            old_material_id
        )

        if target_part_id is None:
            raise RuntimeError(
                f"Missing material BOM part map: "
                f"{src['part_id']}"
            )

        if target_material_id is None:
            raise RuntimeError(
                f"Missing material map: "
                f"{old_material_id}"
            )

        existing = db.execute(
            text("""
                SELECT id
                FROM material_bom_lines
                WHERE part_id = :part_id
                  AND material_id = :material_id
                  AND COALESCE(sort_order, -1)
                      = COALESCE(:sort_order, -1)
                ORDER BY id
                LIMIT 1
            """),
            {
                "part_id": target_part_id,
                "material_id": target_material_id,
                "sort_order": src.get("sort_order"),
            },
        ).scalar()

        if existing is not None:
            match_count += 1
            continue

        payload = filtered_payload(
            "material_bom_lines",
            src,
        )

        payload["part_id"] = target_part_id
        payload["material_id"] = (
            target_material_id
        )

        insert_returning_id(
            db,
            "material_bom_lines",
            payload,
        )

        insert_count += 1

    inserted["material_bom_lines"] = insert_count
    matched["material_bom_lines"] = match_count
    inserted["material_bom_lines_skipped"] = skipped_count


    # ========================================================
    # TEST SUMMARY
    # ========================================================

    print()
    print("=" * 72)
    print("IMPORT TEST SUMMARY — ROLLBACK MODE")
    print("=" * 72)

    all_keys = sorted(
        set(inserted) | set(matched)
    )

    for key in all_keys:

        print(
            f"{key:32} "
            f"INSERT={inserted.get(key, 0):3} "
            f"MATCH={matched.get(key, 0):3}"
        )

    print("=" * 72)

    print(
        "Excluded product codes:",
        sorted(EXCLUDED_PRODUCT_CODES),
    )

    print(
        "Excluded material category codes:",
        sorted(EXCLUDED_MATERIAL_CATEGORY_CODES),
    )

    print("=" * 72)

    # ========================================================
    # CRITICAL: TEST ONLY
    # ========================================================

    db.rollback()

    print("ROLLBACK_OK")
    print("NO DATABASE WRITES WERE SAVED")


except Exception as exc:

    db.rollback()

    print()
    print("IMPORT_TEST_ROLLBACK")
    print(
        f"{type(exc).__name__}: {exc}"
    )

    raise


finally:
    db.close()
