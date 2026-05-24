from auth.security import hash_password
from models import Material, User


def seed_defaults(db):
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            password_hash=hash_password("1234"),
            role="admin",
        )
        db.add(admin)
    elif not admin.password_hash:
        admin.password_hash = hash_password(admin.password or "1234")
        admin.password = None

    operator = db.query(User).filter(User.username == "operator1").first()
    if not operator:
        operator = User(
            username="operator1",
            password_hash=hash_password("1111"),
            role="operator",
        )
        db.add(operator)
    elif not operator.password_hash:
        operator.password_hash = hash_password(operator.password or "1111")
        operator.password = None

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
