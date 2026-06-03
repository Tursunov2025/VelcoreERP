from auth.security import hash_password
from constants import DEPARTMENTS
from models import Material, MaterialCategory, User
from services.permissions import set_user_permissions
from services.chat_seed import seed_chat_rooms
from services.materials_warehouse import seed_material_categories
from services.material_auto_consumption import seed_consumption_rules
from services.mes_seed import seed_mes_defaults
from services.mobile_app_versions import ensure_default_version


def seed_defaults(db):
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            password_hash=hash_password("1234"),
            role="admin",
            department="Admin",
        )
        db.add(admin)
    else:
        admin.role = "admin"
        admin.department = "Admin"
        if not admin.password_hash:
            admin.password_hash = hash_password(admin.password or "1234")
            admin.password = None

    demo_users = [
        ("kesish1", "1111", "Kesish"),
        ("svarka1", "1111", "Svarka"),
        ("kraska1", "1111", "Kraska"),
        ("upakovka1", "1111", "Upakovka"),
        ("tekshiruv1", "1111", "Tekshiruv"),
        ("ombor1", "1111", "Ombor"),
    ]
    for username, password, department in demo_users:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            db.add(
                User(
                    username=username,
                    password_hash=hash_password(password),
                    role="operator",
                    department=department,
                )
            )
        else:
            user.department = department
            if not user.password_hash:
                user.password_hash = hash_password(password)
                user.password = None

    seed_material_categories(db)

    cat_metal = db.query(MaterialCategory).filter(MaterialCategory.code == "METAL").first()
    cat_paint = db.query(MaterialCategory).filter(MaterialCategory.code == "PAINT").first()
    cat_cons = db.query(MaterialCategory).filter(MaterialCategory.code == "CONS").first()

    default_materials = [
        ("MAT-TEMIR", "Temir profil", "m", 100, 20, cat_metal.id if cat_metal else None, 15000),
        ("MAT-BOYOQ", "Bo'yoq", "l", 50, 10, cat_paint.id if cat_paint else None, 8000),
        ("MAT-SHISHA", "Shisha", "dona", 30, 5, cat_cons.id if cat_cons else None, 12000),
    ]
    for code, name, unit, qty, min_qty, category_id, unit_cost in default_materials:
        existing = db.query(Material).filter(Material.name == name).first()
        if not existing:
            db.add(
                Material(
                    code=code,
                    name=name,
                    unit=unit,
                    category_id=category_id,
                    quantity=qty,
                    min_quantity=min_qty,
                    unit_cost=unit_cost,
                    is_active=True,
                )
            )
        else:
            if not existing.code:
                existing.code = code
            if category_id and not existing.category_id:
                existing.category_id = category_id
            if not existing.unit_cost:
                existing.unit_cost = unit_cost

    db.commit()

    ombor = db.query(User).filter(User.username == "ombor1").first()
    if ombor:
        set_user_permissions(
            db,
            ombor.id,
            {
                "materials_view": True,
                "materials_edit": True,
                "warehouse": True,
            },
        )
        db.commit()

    seed_consumption_rules(db)
    seed_chat_rooms(db)
    seed_mes_defaults(db)
    ensure_default_version(db)
