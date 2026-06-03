"""Phase 8 — mobile auto-update API."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("JWT_SECRET_KEY", "test-p8-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p8_mobile.db")

from fastapi.testclient import TestClient
from database import Base, SessionLocal, engine
from main import app
from models import MobileAppVersion
from services.seed import seed_defaults

Base.metadata.create_all(bind=engine)
db = SessionLocal()
try:
    seed_defaults(db)
    db.query(MobileAppVersion).delete()
    db.commit()
finally:
    db.close()

client = TestClient(app)


def _login():
    r = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_mobile_version_empty():
    r = client.get("/mobile/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version_code"] == 0


def test_publish_and_fetch():
    h = _login()
    pub = client.put(
        "/admin/mobile/versions/publish",
        headers=h,
        json={
            "version_name": "1.0.1",
            "version_code": 2,
            "apk_url": "http://192.168.1.1:8000/uploads/mobile/test.apk",
            "release_notes": "Bug fixes",
            "force_update": True,
        },
    )
    assert pub.status_code == 200, pub.text
    assert pub.json()["version_name"] == "1.0.1"

    r = client.get("/mobile/version")
    assert r.status_code == 200
    body = r.json()
    assert body["latest_version"] == "1.0.1"
    assert body["version_code"] == 2
    assert body["force_update"] is True
    assert "Bug fixes" in body["release_notes"]
    assert body["apk_url"].endswith("test.apk")

    lst = client.get("/admin/mobile/versions", headers=h)
    assert lst.status_code == 200
    assert len(lst.json()["items"]) >= 1


def test_version_code_must_increase():
    h = _login()
    bad = client.put(
        "/admin/mobile/versions/publish",
        headers=h,
        json={
            "version_name": "1.0.0",
            "version_code": 1,
            "apk_url": "http://x/uploads/mobile/a.apk",
        },
    )
    assert bad.status_code == 400


if __name__ == "__main__":
    test_mobile_version_empty()
    test_publish_and_fetch()
    test_version_code_must_increase()
    print("P8 mobile auto-update: ALL TESTS PASSED")
