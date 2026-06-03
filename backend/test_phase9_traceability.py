"""Phase 9 — package traceability, QR labels, warehouse location, dispatch scan."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-phase9")

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesDispatch,
    MesFinishedGoodsInventory,
    MesJobPackage,
    MesProductionJob,
    MesProductCategory,
    MesProductTemplate,
    MesWarehouseLocation,
)
from services.package_traceability import (  # noqa: E402
    LABEL_PATTERN,
    assign_package_location,
    build_passport,
    build_public_tracking,
    create_label_for_package,
    generate_label_code,
)
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


def make_packed_package(db: Session) -> tuple[MesJobPackage, MesProductionJob, MesProductTemplate]:
    suffix = datetime.utcnow().strftime("%H%M%S%f")
    cat = MesProductCategory(name=f"P9 Cat {suffix}", created_by="admin")
    db.add(cat)
    db.flush()
    template = MesProductTemplate(
        category_id=cat.id,
        code=f"Z9-{suffix}",
        name="Z9 Chair",
        length_mm=800,
        width_mm=600,
        height_mm=400,
        created_by="admin",
    )
    db.add(template)
    db.flush()
    job = MesProductionJob(
        job_number=f"JOB-P9-{suffix}",
        template_id=template.id,
        quantity=1.0,
        status="in_progress",
        customer_name="Test Customer",
        created_by="admin",
    )
    db.add(job)
    db.flush()
    pkg = MesJobPackage(
        job_id=job.id,
        package_number=f"PACK-P9-{suffix}-1",
        package_type="box",
        net_weight_kg=6.0,
        gross_weight_kg=6.5,
        status="packed",
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    db.refresh(job)
    db.refresh(template)
    return pkg, job, template


def test_label_code_format_and_images(db: Session):
    code = generate_label_code(db)
    assert LABEL_PATTERN.match(code)
    pkg, job, _template = make_packed_package(db)
    with patch("services.label_printer.send_zpl_to_printer"):
        label = create_label_for_package(db, pkg, username="admin", auto_print=False)
    db.commit()
    assert label.label_code == code
    assert label.barcode_data == code
    assert "/track/package/" in label.qr_data

    passport = build_passport(db, label.label_code)
    assert passport
    assert passport["label_code"] == code
    assert passport["weight_kg"] == 6.0
    assert passport.get("qr_image_base64") or passport.get("barcode_image_base64")


def test_api_passport_location_dispatch_public(client: TestClient, db: Session):
    token = login(client)
    h = auth_headers(token)
    pkg, job, template = make_packed_package(db)
    with patch("services.label_printer.send_zpl_to_printer"):
        label = create_label_for_package(db, pkg, username="admin", auto_print=False)
    db.commit()

    r = client.get(f"/packages/{label.label_code}", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["label_code"] == label.label_code
    assert body["customer"] == "Test Customer"
    assert isinstance(body.get("timeline"), list)

    loc = assign_package_location(
        db,
        label_code=label.label_code,
        warehouse_zone="A",
        rack="R1",
        shelf="S2",
        username="admin",
    )
    db.commit()
    assert loc.warehouse_zone == "A"

    r2 = client.put(
        f"/packages/{label.label_code}/location",
        headers=h,
        json={"warehouse_zone": "B", "rack": "R9", "shelf": "S1"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["warehouse_zone"] == "B"

    loc = MesWarehouseLocation(code="P9-A1", description="P9", created_by="admin")
    db.add(loc)
    db.flush()
    db.add(
        MesFinishedGoodsInventory(
            package_id=pkg.id,
            job_id=job.id,
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
    pkg.status = "placed"
    dispatch = MesDispatch(
        job_id=job.id,
        dispatch_number="DISP-P9-001",
        status="loading",
        created_by="admin",
    )
    db.add(dispatch)
    db.commit()

    r3 = client.post(
        f"/mes/terminal/dispatch/jobs/{job.id}/scan-label",
        headers=h,
        json={"label_code": label.label_code},
    )
    assert r3.status_code == 200, r3.text
    assert r3.json()["status"] == "loaded"
    assert r3.json()["loaded_by"] == "admin"

    pub = client.get(f"/track/package/{label.label_code}")
    assert pub.status_code == 200, pub.text
    pub_body = pub.json()
    assert pub_body["label_code"] == label.label_code
    assert "product" in pub_body
    assert "status" in pub_body
    assert "production_completed_date" in pub_body

    dash = client.get("/traceability/dashboard", headers=h)
    assert dash.status_code == 200
    assert "packages_today" in dash.json()


def main():
    db = setup_db()
    client = TestClient(app)
    test_label_code_format_and_images(db)
    test_api_passport_location_dispatch_public(client, db)
    print("test_phase9_traceability: OK")


if __name__ == "__main__":
    main()
