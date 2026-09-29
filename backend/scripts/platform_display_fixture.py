"""Create explicit E2E-only Platform Administration / Display Center fixture data."""
from __future__ import annotations

import os
import sys
from pathlib import Path

backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend))

from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from models import User, UserIdentityProfile  # noqa: E402
from services.permissions import set_user_permissions  # noqa: E402
from services.super_admin_service import seed_super_admin_defaults  # noqa: E402


def main() -> None:
    if os.getenv("E2E_FIXTURE", "") != "1":
        raise SystemExit("E2E_FIXTURE=1 is required")
    Base.metadata.create_all(engine)
    run_migrations()
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.username == "e2e-platform-owner").first()
        if not owner:
            owner = User(
                username="e2e-platform-owner",
                password_hash=hash_password("E2E-Platform-2026!"),
                role="super_admin",
                department="Admin",
                is_active=True,
            )
            db.add(owner)
        viewer = db.query(User).filter(User.username == "e2e-display-viewer").first()
        if not viewer:
            viewer = User(
                username="e2e-display-viewer",
                password_hash=hash_password("E2E-Viewer-2026!"),
                role="operator",
                department="Display Center",
                is_active=True,
            )
            db.add(viewer)
        db.flush()
        if not db.query(UserIdentityProfile).filter_by(user_id=owner.id).first():
            db.add(UserIdentityProfile(user_id=owner.id, full_name="E2E Platform Owner"))
        if not db.query(UserIdentityProfile).filter_by(user_id=viewer.id).first():
            db.add(UserIdentityProfile(user_id=viewer.id, full_name="E2E Display Viewer"))
        set_user_permissions(db, viewer.id, {"display_center_view": True})
        seed_super_admin_defaults(db)
        db.commit()
        print(f"fixture_ready owner_id={owner.id} viewer_id={viewer.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
