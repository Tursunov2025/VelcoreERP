"""B8 Dispatch terminal integration test (ephemeral)."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-b8-dispatch")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesBomLine,
    MesFinishedGoodsInventory,
    MesJobPackage,
    MesJobRouteStep,
    MesProductionJob,
    MesProductionRoute,
    MesProductionStage,
    MesProductCategory,
    MesProductPart,
    MesProductTemplate,
    MesRouteStep,
    MesWarehouseLocation,
    User,
)
from services.mes_jobs import load_job, release_job_snapshot  # noqa: E402
from services.mes_terminal_common import get_active_step  # noqa: E402
from services.permissions import set_user_permissions  # noqa: E402
from services.seed import seed_defaults  # noqa: E402


def setup_db() -> Session:
    Base.metadata.create_all(bind=engine)
    run_migrations()
    db = SessionLocal()
    seed_defaults(db)
    return db


def login(client: TestClient) -> str:
    r = client.post("/auth/login", json={"username": "admin", "password": "1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def bootstrap_dispatch_job(db: Session) -> tuple[int, list[int]]:
    yuklash = db.query(MesProductionStage).filter(MesProductionStage.name == "Yuklash").first()
    assert yuklash

    cat = MesProductCategory(name="Test Cat B8", created_by="admin")
    db.add(cat)
    db.flush()

    part = MesProductPart(
        part_number="DISP-PART-001",
        name="Dispatch Test Part",
        unit="dona",
        created_by="admin",
    )
    db.add(part)
    db.flush()

    template = MesProductTemplate(
        category_id=cat.id,
        code="DISP-TPL-B8",
        name="Dispatch Test Product",
        created_by="admin",
    )
    db.add(template)
    db.flush()

    db.add(
        MesBomLine(
            template_id=template.id,
            part_id=part.id,
            required_quantity=1.0,
            sort_order=0,
            is_active=True,
        )
    )

    route = MesProductionRoute(
        template_id=template.id,
        name="Dispatch Route",
        version=1,
        is_default=True,
        is_active=True,
        created_by="admin",
    )
    db.add(route)
    db.flush()
    template.default_route_id = route.id

    db.add(MesRouteStep(route_id=route.id, stage_id=yuklash.id, step_order=0, is_required=True))
    db.commit()

    job = MesProductionJob(
        job_number="JOB-B8-TEST",
        customer_name="Test Customer LLC",
        template_id=template.id,
        quantity=1.0,
        status="draft",
        created_by="admin",
    )
    db.add(job)
    db.commit()
    release_job_snapshot(db, job)
    job.status = "in_progress"
    db.commit()
    db.refresh(job)

    loc = db.query(MesWarehouseLocation).filter(MesWarehouseLocation.code == "A-01-01").first()
    assert loc

    pkg_ids = []
    for i in range(1, 3):
        pkg = MesJobPackage(
            job_id=job.id,
            package_number=f"PACK-JOB-B8-TEST-00{i}",
            package_type="Karton",
            net_weight_kg=5.0,
            gross_weight_kg=6.0,
            status="placed",
            location_id=loc.id,
            placed_at=datetime.utcnow(),
        )
        db.add(pkg)
        db.flush()
        pkg_ids.append(pkg.id)
        db.add(
            MesFinishedGoodsInventory(
                job_id=job.id,
                package_id=pkg.id,
                template_id=template.id,
                product_code=template.code,
                product_name=template.name,
                location_id=loc.id,
                quantity=1.0,
                status="in_stock",
                placed_at=datetime.utcnow(),
                created_by="admin",
            )
        )
    db.commit()
    return job.id, pkg_ids


def run_tests() -> None:
    db = setup_db()
    client = TestClient(app)
    token = login(client)
    headers = auth_headers(token)

    admin = db.query(User).filter(User.username == "admin").first()
    set_user_permissions(db, admin.id, {"mes_terminal_dispatch": True, "mes_view": True})
    db.commit()

    r = client.get("/mes/terminal/dispatch/dashboard", headers=headers)
    assert r.status_code == 200, r.text

    job_id, package_ids = bootstrap_dispatch_job(db)

    r = client.get("/mes/terminal/dispatch/queue", headers=headers)
    assert r.status_code == 200, r.text
    assert any(j["id"] == job_id for j in r.json()["jobs"])

    r = client.post(f"/mes/terminal/dispatch/jobs/{job_id}/accept", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dispatch"]["dispatch_number"] == "DISP-JOB-B8-TEST"
    assert data["dispatch"]["customer_name"] == "Test Customer LLC"
    assert data["dispatch"]["package_count"] == 2

    r = client.post(f"/mes/terminal/dispatch/jobs/{job_id}/start", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["dispatch"]["status"] == "loading"

    r = client.put(
        f"/mes/terminal/dispatch/jobs/{job_id}/transport",
        headers=headers,
        json={
            "vehicle_number": "01A123BC",
            "driver_name": "Ali Valiyev",
            "driver_phone": "+998901234567",
            "transport_company": "Azmus Logistika",
        },
    )
    assert r.status_code == 200, r.text

    for pkg_id in package_ids:
        r = client.post(
            f"/mes/terminal/dispatch/jobs/{job_id}/packages/{pkg_id}/load",
            headers=headers,
        )
        assert r.status_code == 200, r.text

    r = client.post(f"/mes/terminal/dispatch/jobs/{job_id}/ship", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["dispatch"]["status"] == "shipped"
    assert r.json()["dispatch"]["ship_date"] is not None

    r = client.post(f"/mes/terminal/dispatch/jobs/{job_id}/deliver", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["dispatch"]["status"] == "delivered"
    assert r.json()["status"] == "completed"

    job = load_job(db, job_id)
    assert job.status == "completed"
    active = get_active_step(job)
    assert active is None, "All route steps should be complete"

    print("ALL B8 DISPATCH TERMINAL TESTS PASSED")
    db.close()
    try:
        os.unlink(TEST_DB)
    except OSError:
        pass


if __name__ == "__main__":
    run_tests()
