"""Seed Velcore Driver profiles — 3 ichki + 5 tashqi haydovchi."""
from __future__ import annotations

from models import Driver


INTERNAL_DRIVERS = [
    ("Ichki haydovchi 1", "998901111101"),
    ("Ichki haydovchi 2", "998901111102"),
    ("Ichki haydovchi 3", "998901111103"),
]

EXTERNAL_DRIVERS = [
    ("Tashqi fura 1", "998902222201"),
    ("Tashqi fura 2", "998902222202"),
    ("Tashqi fura 3", "998902222203"),
    ("Tashqi fura 4", "998902222204"),
    ("Tashqi fura 5", "998902222205"),
]


def seed_driver_profiles(db) -> None:
    """Ensure driver slots exist (profiles only — ERP User alohida yaratiladi)."""
    for name, phone in INTERNAL_DRIVERS:
        _ensure_driver(db, name, phone, "internal")
    for name, phone in EXTERNAL_DRIVERS:
        _ensure_driver(db, name, phone, "external")
    db.commit()


def _ensure_driver(db, full_name: str, phone: str, driver_type: str) -> None:
    existing = db.query(Driver).filter(Driver.phone == phone).first()
    if existing:
        if not getattr(existing, "driver_type", None):
            existing.driver_type = driver_type
        return
    db.add(
        Driver(
            full_name=full_name,
            phone=phone,
            driver_type=driver_type,
            status="active",
        )
    )
