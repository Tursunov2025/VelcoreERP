from auth.security import hash_password
from constants import DEPARTMENTS
from models import Material, User
from services.chat_seed import seed_chat_rooms


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

    default_materials = [
        ("Temir profil", "m", 100, 20),
        ("Bo'yoq", "l", 50, 10),
        ("Shisha", "dona", 30, 5),
    ]
    for name, unit, qty, min_qty in default_materials:
        if not db.query(Material).filter(Material.name == name).first():
            db.add(
                Material(
                    name=name,
                    unit=unit,
                    quantity=qty,
                    min_quantity=min_qty,
                )
            )

    db.commit()
    seed_chat_rooms(db)
