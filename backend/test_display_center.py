"""Focused authoritative Display Center contract tests on disposable SQLite."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
root = Path(tempfile.mkdtemp(prefix="velcore-display-center-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{db_file.replace(chr(92), '/')}",
    "DB_PATH": db_file.replace(chr(92), "/"),
    "DATA_ROOT": str(root),
    "UPLOAD_PATH": str(root / "uploads"),
    "BACKUP_PATH": str(root / "backups"),
    "LOG_PATH": str(root / "logs"),
    "JWT_SECRET_KEY": "display-center-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from auth.security import hash_password  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import AuditLog, DisplayHeartbeat, User  # noqa: E402
from services.permissions import set_user_permissions  # noqa: E402
from services.super_admin_service import seed_super_admin_defaults  # noqa: E402


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": "11111111"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_display_center_full_contract():
    Base.metadata.create_all(engine)
    run_migrations()
    db = SessionLocal()
    try:
        owner = User(username="display-owner", password_hash=hash_password("11111111"), role="super_admin", department="Admin")
        viewer = User(username="display-viewer", password_hash=hash_password("11111111"), role="operator", department="Display Center")
        outsider = User(username="display-outsider", password_hash=hash_password("11111111"), role="operator", department="CRM")
        db.add_all([owner, viewer, outsider]); db.flush()
        set_user_permissions(db, viewer.id, {"display_center_view": True})
        seed_super_admin_defaults(db); db.commit()

        client = TestClient(app)
        owner_h, viewer_h, outsider_h = login(client, "display-owner"), login(client, "display-viewer"), login(client, "display-outsider")
        assert client.get("/display-center/dashboard").status_code == 401
        assert client.get("/display-center/dashboard", headers=outsider_h).status_code == 403
        assert client.get("/display-center/dashboard", headers=viewer_h).status_code == 200
        assert client.post("/display-center/widgets", headers=viewer_h, json={"key":"blocked","name":"Blocked","widget_type":"clock"}).status_code == 403

        template_payload = {"name":"Factory status", "category":"factory", "canvas_json":{"width":1920,"height":1080,"grid":20}, "layout_json":{"widgets":[]}, "is_active":True}
        template = client.post("/display-center/templates", headers=owner_h, json=template_payload)
        assert template.status_code == 200, template.text
        template_id = template.json()["id"]
        clone = client.post(f"/display-center/templates/{template_id}/clone", headers=owner_h, json={"name":"Factory status copy"})
        assert clone.status_code == 200, clone.text

        widget = client.post("/display-center/widgets", headers=owner_h, json={"key":"factory-clock","name":"Factory clock","widget_type":"clock","settings_json":{"x":80,"y":80,"width":400,"height":160},"is_active":True})
        assert widget.status_code == 200, widget.text
        widget_id = widget.json()["id"]
        duplicate_widget = client.post("/display-center/widgets", headers=owner_h, json={"key":"factory-clock","name":"Duplicate","widget_type":"clock"})
        assert duplicate_widget.status_code == 409 and duplicate_widget.json()["detail"]["code"] == "widget_key_exists"

        playlist = client.post("/display-center/playlists", headers=owner_h, json={"name":"Main rotation","description":"","template_key":"custom","template_id":template_id,"is_active":True})
        assert playlist.status_code == 200, playlist.text
        playlist_id = playlist.json()["id"]
        item_payload = {"item_type":"clock","widget_id":widget_id,"media_id":None,"settings_json":{"x":20,"y":20,"width":500,"height":180},"position":0,"duration_seconds":10,"transition":"fade","repeat":True}
        item = client.post(f"/display-center/playlists/{playlist_id}/items", headers=owner_h, json=item_payload)
        assert item.status_code == 200, item.text
        item_id = item.json()["id"]
        item_payload["duration_seconds"] = 20
        assert client.put(f"/display-center/playlist-items/{item_id}", headers=owner_h, json=item_payload).json()["duration_seconds"] == 20

        display = client.post("/display-center/displays", headers=owner_h, json={"name":"Shop floor 1","code":"SHOP-1","location":"Factory","resolution":"1920x1080","orientation":"landscape","playlist_id":playlist_id,"is_active":True})
        assert display.status_code == 200, display.text
        display_id = display.json()["id"]
        assert client.post("/display-center/displays", headers=owner_h, json={"name":"Duplicate","code":"SHOP-1"}).status_code == 409

        now = datetime.now(timezone.utc)
        schedule_payload = {"playlist_id":playlist_id,"display_id":display_id,"starts_at":(now-timedelta(minutes=1)).isoformat(),"ends_at":(now+timedelta(hours=1)).isoformat(),"weekdays_json":[],"start_time":"00:00","end_time":"23:59","priority":10,"is_active":True}
        schedule = client.post("/display-center/schedules", headers=owner_h, json=schedule_payload)
        assert schedule.status_code == 200, schedule.text
        schedule_id = schedule.json()["id"]
        assert client.post("/display-center/schedules", headers=owner_h, json=schedule_payload).status_code == 409
        invalid_schedule = {**schedule_payload, "starts_at":now.isoformat(), "ends_at":(now-timedelta(minutes=1)).isoformat()}
        assert client.post("/display-center/schedules", headers=owner_h, json=invalid_schedule).status_code == 422

        runtime = client.get("/display-center/display/SHOP-1")
        assert runtime.status_code == 200, runtime.text
        assert runtime.json()["playlist"]["id"] == playlist_id and runtime.json()["schedule"]["id"] == schedule_id
        heartbeat = client.post("/display-center/heartbeat", json={"displayCode":"SHOP-1","connection":"wifi","resolution":"1920x1080","browser":"test","playlist":"Main rotation","uptime":30,"fullscreen":True})
        assert heartbeat.status_code == 200, heartbeat.text
        assert client.get("/display-center/monitoring", headers=viewer_h).json()["items"][0]["effective_status"] == "online"
        db.expire_all()
        assert db.query(DisplayHeartbeat).count() == 1

        settings = client.get("/display-center/settings", headers=owner_h).json()
        settings_update = {**settings, "refresh_interval_seconds":30, "offline_after_seconds":90}
        saved_settings = client.put("/display-center/settings", headers=owner_h, json=settings_update)
        assert saved_settings.status_code == 200, saved_settings.text
        assert client.put("/display-center/settings", headers=owner_h, json=settings_update).status_code == 409

        unsafe = client.post("/display-center/media/upload", headers=owner_h, files={"file":("bad.png", b"not-a-png", "image/png")})
        assert unsafe.status_code == 415 and unsafe.json()["detail"]["code"] == "unsupported_media"
        safe = client.post("/display-center/media/upload", headers=owner_h, files={"file":("safe.png", b"\x89PNG\r\n\x1a\nTEST", "image/png")})
        assert safe.status_code == 200, safe.text
        media_id = safe.json()["id"]
        assert client.delete(f"/display-center/media/{media_id}", headers=owner_h).status_code == 200

        assert client.delete(f"/display-center/widgets/{widget_id}", headers=owner_h).status_code == 409
        assert client.delete(f"/display-center/templates/{template_id}", headers=owner_h).status_code == 409
        assert client.delete(f"/display-center/playlists/{playlist_id}", headers=owner_h).status_code == 409
        assert client.delete(f"/display-center/displays/{display_id}", headers=owner_h).status_code == 409

        assert client.delete(f"/display-center/schedules/{schedule_id}", headers=owner_h).status_code == 200
        assert client.delete(f"/display-center/playlist-items/{item_id}", headers=owner_h).status_code == 200
        assert client.delete(f"/display-center/displays/{display_id}", headers=owner_h).status_code == 200
        assert client.delete(f"/display-center/playlists/{playlist_id}", headers=owner_h).status_code == 200
        assert client.delete(f"/display-center/widgets/{widget_id}", headers=owner_h).status_code == 200
        assert client.delete(f"/display-center/templates/{template_id}", headers=owner_h).status_code == 200

        db.expire_all()
        assert db.query(AuditLog).filter(AuditLog.details.like('%"module": "display_center"%')).count() >= 15
        assert not list((root / "uploads" / "display-center").glob("*"))
    finally:
        db.close()
