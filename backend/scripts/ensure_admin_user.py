#!/usr/bin/env python3
"""Ensure admin user exists with known password (production bootstrap)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.security import hash_password
from database import SessionLocal
from models import User
from services.seed import seed_defaults


def main() -> int:
    password = os.getenv("ADMIN_PASSWORD", "1234")
    db = SessionLocal()
    try:
        seed_defaults(db)
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password(password),
                role="admin",
                department="Admin",
                is_active=True,
            )
            db.add(admin)
        else:
            admin.role = "admin"
            admin.department = "Admin"
            admin.is_active = True
            admin.password_hash = hash_password(password)
            admin.password = None
        db.commit()
        print(f"OK admin user ready (password from ADMIN_PASSWORD env, default 1234)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
