"""Focused Platform Administration security and persistence tests on isolated SQLite."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
root = Path(tempfile.mkdtemp(prefix="velcore-platform-admin-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{db_file.replace(chr(92), '/')}", "DB_PATH": db_file.replace(chr(92), "/"),
    "DATA_ROOT": str(root), "UPLOAD_PATH": str(root / "uploads"), "BACKUP_PATH": str(root / "backups"),
    "LOG_PATH": str(root / "logs"), "JWT_SECRET_KEY": "platform-administration-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import AuditLog, Role, SystemSetting, User  # noqa: E402
from services.permissions import set_user_permissions  # noqa: E402
from services.platform_administration import append_audit  # noqa: E402
from services.super_admin_service import seed_super_admin_defaults  # noqa: E402
from routers.platform_admin_router import AppearanceUpdate  # noqa: E402


def login(client, username, password="11111111"):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_platform_administration():
    Base.metadata.create_all(engine); run_migrations(); db = SessionLocal()
    try:
        owner = User(username="platform-owner", password_hash=hash_password("11111111"), role="admin", department="Admin")
        delegated = User(username="platform-delegated", password_hash=hash_password("11111111"), role="operator", department="Kesish")
        outsider = User(username="platform-outsider", password_hash=hash_password("11111111"), role="operator", department="Kraska")
        db.add_all([owner, delegated, outsider]); db.flush()
        set_user_permissions(db, delegated.id, {"platform_admin_view": True, "platform_admin_roles": True, "platform_admin_audit": True, "platform_admin_backup": True, "platform_admin_security": True, "platform_admin_manage": True})
        db.add(SystemSetting(key="telegram_bot_token", value="test-telegram-secret-never-return"))
        seed_super_admin_defaults(db); db.commit()
        client = TestClient(app); owner_h = login(client, "platform-owner"); delegated_h = login(client, "platform-delegated"); outsider_h = login(client, "platform-outsider")

        assert client.get("/admin/platform/access", headers=delegated_h).status_code == 200
        assert client.get("/admin/platform/access", headers=outsider_h).status_code == 403
        assert client.get("/admin/platform/roles").status_code == 401
        assert client.get("/admin/platform/roles", headers=outsider_h).status_code == 403

        departments = client.get("/admin/identity/departments", headers=owner_h)
        assert departments.status_code == 200 and any(item["name"] == "Admin" for item in departments.json()["items"])
        created_department = client.post("/admin/identity/departments", headers=owner_h, json={"name": "Quality Lab"})
        assert created_department.status_code == 200, created_department.text
        renamed_department = client.put("/admin/identity/departments/Quality%20Lab", headers=owner_h, json={"name": "Quality Office"})
        assert renamed_department.status_code == 200, renamed_department.text
        assert client.delete("/admin/identity/departments/Quality%20Office", headers=owner_h).status_code == 200
        activity = client.get("/admin/identity/activity", headers=owner_h)
        assert activity.status_code == 200 and any(item["action"] == "department.create" for item in activity.json()["items"])

        sessions = client.get("/admin/identity/sessions", headers=owner_h)
        assert sessions.status_code == 200 and len(sessions.json()["items"]) >= 3
        outsider_session = next(item for item in sessions.json()["items"] if item["username"] == "platform-outsider")
        assert client.post(f"/admin/identity/sessions/{outsider_session['id']}/revoke", headers=owner_h).status_code == 200
        assert client.get("/admin/platform/access", headers=outsider_h).status_code == 401
        outsider_h = login(client, "platform-outsider")

        validation = client.put(f"/admin/identity/users/{owner.id}", headers=owner_h, json={"username": "x", "password": "short"})
        assert validation.status_code == 422
        errors = validation.json()["detail"]
        assert {tuple(item["loc"])[-1] for item in errors} == {"username", "password"}
        owner_payload = {"username": owner.username, "role": owner.role, "department": owner.department, "is_active": False}
        self_lockout = client.put(f"/admin/identity/users/{owner.id}", headers=owner_h, json=owner_payload)
        assert self_lockout.status_code == 409 and self_lockout.json()["detail"]["code"] == "self_lockout"
        assert client.post(f"/admin/identity/users/{owner.id}/status?active=false", headers=owner_h).status_code == 409

        created = client.post("/admin/platform/roles", headers=delegated_h, json={"role_key": "auditor_test", "label": "Auditor Test", "permissions": {"platform_admin_view": True}})
        assert created.status_code == 200, created.text
        role_id = created.json()["id"]
        assigned = User(username="assigned-role", password_hash=hash_password("11111111"), role="auditor_test", department="Finance")
        db.add(assigned); db.commit()
        assigned_h = login(client, "assigned-role")
        assert client.get("/admin/platform/access", headers=assigned_h).status_code == 200
        assert client.post("/admin/platform/roles", headers=assigned_h, json={"role_key": "forbidden_role", "label": "Forbidden"}).status_code == 403
        assert client.delete(f"/admin/platform/roles/{role_id}", headers=owner_h).status_code == 409
        assigned.role = "operator"; db.commit()
        assert client.delete(f"/admin/platform/roles/{role_id}", headers=owner_h).status_code == 200

        super_role = db.query(Role).filter_by(role_key="super_admin").one()
        locked = client.put(f"/admin/platform/roles/{super_role.id}", headers=owner_h, json={"is_active": False})
        assert locked.status_code == 409
        admin_role = db.query(Role).filter_by(role_key="admin").one()
        assert client.put(f"/admin/platform/roles/{admin_role.id}", headers=owner_h, json={"permissions": {}}).status_code == 409

        appearance = client.get("/admin/platform/appearance", headers=owner_h).json()
        valid_appearance = {key: appearance[key] for key in AppearanceUpdate.model_fields if key in appearance}
        assert client.put("/admin/platform/appearance", headers=outsider_h, json=valid_appearance).status_code == 403
        assert client.put("/admin/platform/appearance", headers=owner_h, json={**valid_appearance, "custom_css": "body{}"}).status_code == 422
        inaccessible = {**valid_appearance, "color_button": "#ffffff", "color_button_text": "#ffffff"}
        assert client.put("/admin/platform/appearance", headers=owner_h, json=inaccessible).status_code == 422
        saved = client.put("/admin/platform/appearance", headers=owner_h, json={"app_name": "Velcore Test", "short_name": "VT", "color_primary": "#123456", "color_secondary": "#abcdef", "theme_mode": "system", "interface_density": "compact", "login_footer": "Test", "version": appearance["version"]})
        assert saved.status_code == 200, saved.text
        public_branding = client.get("/branding")
        assert public_branding.status_code == 200 and public_branding.json()["login_footer"] == "Test"
        conflict = client.put("/admin/platform/appearance", headers=owner_h, json={"app_name": "Conflict", "version": appearance["version"]})
        assert conflict.status_code == 409, conflict.text

        navigation = client.get("/admin/platform/navigation", headers=owner_h).json()
        nav_item = navigation["items"][0]
        nav_saved = client.put(f"/admin/platform/navigation/{nav_item['id']}", headers=owner_h, json={
            "label": nav_item["label"], "icon": "dashboard", "visible": nav_item["visible"],
            "sort_order": nav_item["sort_order"], "permissions": nav_item["permissions"],
        })
        assert nav_saved.status_code == 200, nav_saved.text

        bad_logo = client.post("/admin/platform/appearance/logo", headers=owner_h, files={"file": ("bad.svg", b"<svg><script>alert(1)</script></svg>", "image/svg+xml")})
        assert bad_logo.status_code == 415
        integrations = client.get("/admin/platform/integrations", headers=owner_h)
        assert integrations.status_code == 200
        assert "test-telegram-secret-never-return" not in integrations.text

        modules = client.get("/admin/platform/modules", headers=owner_h).json()
        core = next(item for item in modules["items"] if item["module_key"] == "platform_administration")
        assert client.put(f"/admin/platform/modules/{core['module_key']}", headers=owner_h, json={"state": "disabled", "version": modules["version"]}).status_code == 409
        dependency = client.put("/admin/platform/modules/crm", headers=owner_h, json={"state": "disabled", "version": modules["version"]})
        assert dependency.status_code == 409 and "finance" in dependency.text
        disabled = client.put("/admin/platform/modules/orders", headers=owner_h, json={"state": "disabled", "version": modules["version"]})
        assert disabled.status_code == 200, disabled.text
        assert client.get("/orders", headers=owner_h).status_code == 404
        enabled = client.put("/admin/platform/modules/orders", headers=owner_h, json={"state": "enabled", "version": disabled.json()["version"]})
        assert enabled.status_code == 200, enabled.text

        security = client.get("/admin/platform/security", headers=owner_h).json()
        bad_origin = client.put("/admin/platform/security", headers=owner_h, json={**{key: security[key] for key in ("minimum_password_length", "login_attempt_limit", "lockout_minutes", "session_expiration_minutes", "require_password_change", "secure_cookie_required")}, "allowed_cors_origins": ["javascript:alert(1)"], "confirmation": "APPLY SECURITY POLICY", "version": security["version"]})
        assert bad_origin.status_code == 422
        security_payload = {**{key: security[key] for key in ("minimum_password_length", "login_attempt_limit", "lockout_minutes", "session_expiration_minutes", "require_password_change", "secure_cookie_required", "allowed_cors_origins")}, "confirmation": "APPLY SECURITY POLICY", "version": security["version"]}
        security_saved = client.put("/admin/platform/security", headers=owner_h, json=security_payload)
        assert security_saved.status_code == 200, security_saved.text
        assert client.put("/admin/platform/security", headers=owner_h, json=security_payload).status_code == 409

        append_audit(db, actor="platform-owner", action="redaction.test", entity_type="test", details={"password": "never-store-me", "nested": {"api_key": "also-secret", "safe": "visible"}}); db.commit()
        audit = client.get("/admin/platform/audit", headers=owner_h, params={"action": "redaction.test"}).json()["items"][0]
        encoded = str(audit)
        assert "never-store-me" not in encoded and "also-secret" not in encoded and "[REDACTED]" in encoded

        db.add(AuditLog(username="legacy-user", action="legacy.metadata", entity_type="legacy", details="1"))
        db.commit()
        legacy_audit = client.get("/admin/platform/audit", headers=owner_h, params={"action": "legacy.metadata"})
        assert legacy_audit.status_code == 200, legacy_audit.text
        assert legacy_audit.json()["items"][0]["details"] == 1

        backup = client.post("/admin/platform/backups", headers=owner_h)
        assert backup.status_code == 200, backup.text
        preflight = client.post(f"/admin/platform/backups/{backup.json()['name']}/preflight", headers=owner_h)
        assert preflight.status_code == 200 and preflight.json()["valid"] is True and preflight.json()["restore_supported"] is False
        print("test_platform_administration: OK")
    finally:
        db.close()


if __name__ == "__main__": test_platform_administration()
