"""End-to-end API flow for Lazer surplus into reusable SVARKA stock."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

test_db = os.getenv("DETAIL_STOCK_E2E_DB") or tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{test_db.replace(chr(92), '/')}"
test_root = Path(tempfile.mkdtemp(prefix="velcore-stock-e2e-"))
os.environ["DATA_ROOT"] = str(test_root)
os.environ["DB_PATH"] = test_db.replace(chr(92), "/")
os.environ["UPLOAD_PATH"] = str(test_root / "uploads")
os.environ["BACKUP_PATH"] = str(test_root / "backups")
os.environ["LOG_PATH"] = str(test_root / "logs")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-detail-stock")

backend = Path(__file__).resolve().parent
sys.path.insert(0, str(backend))

from fastapi.testclient import TestClient  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesBomLine, MesProductionJob, MesProductionRoute, MesProductionStage,
    MesProductCategory, MesProductPart, MesProductTemplate, MesRouteStep,
    User, WarehouseTransaction,
)
from services.permissions import set_user_permissions  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


def _headers(client: TestClient) -> dict:
    response = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_job(db, part, suffix: str) -> int:
    lazer = db.query(MesProductionStage).filter_by(name="Lazer").one()
    category = MesProductCategory(name=f"Stock E2E {suffix}", created_by="admin")
    db.add(category); db.flush()
    template = MesProductTemplate(category_id=category.id, code=f"STOCK-E2E-{suffix}", name="Stock E2E product", created_by="admin")
    db.add(template); db.flush()
    db.add(MesBomLine(template_id=template.id, part_id=part.id, required_quantity=1, sort_order=0, is_active=True))
    route = MesProductionRoute(template_id=template.id, name="Lazer route", version=1, is_default=True, is_active=True, created_by="admin")
    db.add(route); db.flush(); template.default_route_id = route.id
    db.add(MesRouteStep(route_id=route.id, stage_id=lazer.id, step_order=0, is_required=True))
    job = MesProductionJob(job_number=f"JOB-STOCK-E2E-{suffix}", template_id=template.id, quantity=1, status="draft", created_by="admin")
    db.add(job); db.commit()
    return job.id


def main() -> None:
    Base.metadata.create_all(bind=engine); run_migrations()
    db = SessionLocal()
    try:
        seed_defaults(db)
        admin = db.query(User).filter_by(username="admin").one()
        set_user_permissions(db, admin.id, {"mes_terminal_lazer": True, "mes_edit": True, "mes_jobs_manage": True, "mes_view": True, "warehouse": True})
        part = MesProductPart(part_number="SV-E2E-01", name="SVARKA reusable detail", unit="dona", created_by="admin")
        db.add(part); db.commit()

        client = TestClient(app)
        headers = _headers(client)
        laser_job_id = _create_job(db, part, "LASER")
        assert client.post(f"/mes/jobs/{laser_job_id}/release", headers=headers).status_code == 200
        assert client.post(f"/mes/terminal/lazer/jobs/{laser_job_id}/accept", headers=headers).status_code == 200
        assert client.post(f"/mes/terminal/lazer/jobs/{laser_job_id}/start", headers=headers).status_code == 200
        job = client.get(f"/mes/terminal/lazer/jobs/{laser_job_id}", headers=headers).json()
        line_id = job["bom_lines"][0]["id"]

        update = client.put(f"/mes/terminal/lazer/jobs/{laser_job_id}/quantities", headers=headers, json={"lines": [{"bom_line_id": line_id, "completed_quantity": 2}]})
        assert update.status_code == 200, update.text
        assert update.json()["surplus_candidates"] == [{"bom_line_id": line_id, "part_number": "SV-E2E-01", "part_name": "SVARKA reusable detail", "required_quantity": 1.0, "completed_quantity": 2.0, "surplus_quantity": 1.0}]

        # Lazer operator's "Ha, skladga qo'shish" confirmation creates one IN.
        first_in = client.post("/warehouse/stock/in", headers=headers, params={"job_id": laser_job_id, "bom_line_id": line_id, "quantity": 1})
        assert first_in.status_code == 200, first_in.text
        repeated_in = client.post("/warehouse/stock/in", headers=headers, params={"job_id": laser_job_id, "bom_line_id": line_id, "quantity": 1})
        assert repeated_in.status_code in (400, 409), repeated_in.text
        assert len(db.query(WarehouseTransaction).filter_by(operation="IN").all()) == 1

        # Releasing another MES job reserves the available one unit and exposes TAYYOR.
        consumer_job_id = _create_job(db, part, "CONSUMER")
        released = client.post(f"/mes/jobs/{consumer_job_id}/release", headers=headers)
        assert released.status_code == 200, released.text
        line = released.json()["bom_lines"][0]
        assert line["availability_status"] == "TAYYOR", line
        assert line["stock_quantity"] == 1 and line["production_quantity"] == 0
        warehouse = client.get("/warehouse/stock", headers=headers)
        assert warehouse.status_code == 200
        assert warehouse.json()[0]["available_quantity"] == 0

        cancelled = client.put(f"/mes/jobs/{consumer_job_id}/status", headers=headers, json={"status": "cancelled"})
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["bom_lines"][0]["production_quantity"] == 1
        warehouse = client.get("/warehouse/stock", headers=headers)
        assert warehouse.json()[0]["available_quantity"] == 1

        partial_job_id = _create_job(db, part, "PARTIAL")
        partial_job = db.query(MesProductionJob).filter_by(id=partial_job_id).one()
        partial_job.quantity = 2
        db.commit()
        partial = client.post(f"/mes/jobs/{partial_job_id}/release", headers=headers)
        assert partial.status_code == 200, partial.text
        assert partial.json()["bom_lines"][0]["availability_status"] == "QISMAN TAYYOR"

        no_stock_job_id = _create_job(db, part, "NO-STOCK")
        no_stock = client.post(f"/mes/jobs/{no_stock_job_id}/release", headers=headers)
        assert no_stock.status_code == 200, no_stock.text
        assert no_stock.json()["bom_lines"][0]["availability_status"] == "ISHLAB CHIQARISH KERAK"

        assert client.put(f"/mes/jobs/{partial_job_id}/status", headers=headers, json={"status": "cancelled"}).status_code == 200
        operations = {row.operation for row in db.query(WarehouseTransaction).all()}
        assert {"IN", "RESERVE", "RELEASE"}.issubset(operations)
        print("test_svarshik_detail_stock_e2e: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
