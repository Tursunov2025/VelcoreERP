"""P5 Central system settings integration test (ephemeral)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-p5-settings")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from auth.security import get_access_token_expire_minutes  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from services.seed import seed_defaults  # noqa: E402
from services.settings_cache import get_cached_setting, refresh_settings_cache  # noqa: E402
from services.settings_runtime import get_production_stages  # noqa: E402


def setup_db() -> Session:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    seed_defaults(db)
    refresh_settings_cache(db)
    return db


def login(client: TestClient) -> str:
    r = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_p5_central_settings():
    db = setup_db()
    client = TestClient(app)
    token = login(client)
    headers = auth_headers(token)

    # Non-admin denied
    op = client.post("/auth/login", json={"username": "kesish1", "password": "1111"})
    op_headers = auth_headers(op.json()["access_token"])
    denied = client.get("/admin/settings/company", headers=op_headers)
    assert denied.status_code == 403

    # Company settings
    company = client.get("/admin/settings/company", headers=headers)
    assert company.status_code == 200
    assert "company_name" in company.json()

    updated = client.put(
        "/admin/settings/company",
        headers=headers,
        json={"company_name": "Azmus Test Co", "company_phone": "+998901234567"},
    )
    assert updated.status_code == 200
    assert updated.json()["company_name"] == "Azmus Test Co"

    refresh_settings_cache(db)
    assert get_cached_setting("company_name", db=db) == "Azmus Test Co"

    # Production settings live read
    stages_payload = json.dumps(["Kesish", "Svarka", "TestStage"], ensure_ascii=False)
    prod = client.put(
        "/admin/settings/production",
        headers=headers,
        json={"production_stages_json": stages_payload},
    )
    assert prod.status_code == 200
    refresh_settings_cache(db)
    assert "TestStage" in get_production_stages(db)

    # Materials settings
    mat = client.put(
        "/admin/settings/materials",
        headers=headers,
        json={"materials_auto_consume_enabled": "false"},
    )
    assert mat.status_code == 200

    # Costing settings
    cost = client.get("/admin/settings/costing", headers=headers)
    assert cost.status_code == 200
    assert "costing_currency_symbol" in cost.json()

    # Backup settings affect JWT cache
    jwt = client.put(
        "/admin/settings/backup",
        headers=headers,
        json={"jwt_access_minutes": "120"},
    )
    assert jwt.status_code == 200
    refresh_settings_cache(db)
    assert get_access_token_expire_minutes() == 120

    # Export / import bundle
    exported = client.get("/admin/settings/export", headers=headers)
    assert exported.status_code == 200
    bundle = exported.json()
    assert bundle["version"] == 1
    assert "settings" in bundle

    imported = client.post(
        "/admin/settings/import",
        headers=headers,
        json={"settings": bundle["settings"], "merge": True},
    )
    assert imported.status_code == 200

    # All domain endpoints
    for path in (
        "/admin/settings/warehouse",
        "/admin/settings/materials",
        "/admin/settings/backup",
        "/admin/settings/system",
    ):
        assert client.get(path, headers=headers).status_code == 200

    db.close()
    print("P5 central system settings: ALL TESTS PASSED")


if __name__ == "__main__":
    test_p5_central_settings()
