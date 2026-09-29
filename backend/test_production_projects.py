"""Isolated multi-product production-project foundation tests."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
TEST_ROOT = Path(tempfile.mkdtemp(prefix="velcore-projects-"))
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.replace(chr(92), '/')}"
os.environ["DB_PATH"] = TEST_DB
os.environ["DATA_ROOT"] = str(TEST_ROOT)
os.environ["DATABASE_GUARD"] = "false"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "project-foundation-test-secret"

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    AuditLog, MesBomLine, MesProductionJob, MesProductionRoute,
    MesProductionStage, MesProductPart, MesProductTemplate, MesRouteStep,
    ProductionProject, ProductionProjectLine, ProjectDetailRequirement,
    ProjectLineBomSnapshot, ProjectReleaseSnapshot, ProjectStockAllocation,
    User, WarehouseStock, WarehouseTransaction,
)
from auth.security import hash_password  # noqa: E402


def setup_data():
    Base.metadata.create_all(engine); run_migrations()
    db = SessionLocal()
    admin = User(username="project-admin", password_hash=hash_password("Project123!"), role="admin", department="Admin")
    operator = User(username="project-viewer", password_hash=hash_password("Viewer123!"), role="operator", department="Kesish")
    db.add_all([admin, operator])
    stage = MesProductionStage(name="PROJECT-LAZER", department="Kesish", is_active=True, is_system=True)
    common = MesProductPart(part_number="SHARED-X", name="Shared detail", created_by="test")
    db.add_all([stage, common]); db.flush()
    products = []
    for index in range(1, 21):
        product = MesProductTemplate(code=f"PRD-{index:02d}", name=f"Product {index}", created_by="test")
        unique = MesProductPart(part_number=f"UNIQUE-{index:02d}", name=f"Unique {index}", created_by="test")
        db.add_all([product, unique]); db.flush()
        route = MesProductionRoute(template_id=product.id, name="Project route", version=1, is_default=True, created_by="test")
        db.add(route); db.flush(); product.default_route_id = route.id
        db.add(MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1, department="Kesish"))
        db.add_all([
            MesBomLine(template_id=product.id, part_id=common.id, required_quantity=2, unit="dona", sort_order=1),
            MesBomLine(template_id=product.id, part_id=unique.id, required_quantity=1, unit="dona", sort_order=2),
        ])
        products.append(product)
    missing = MesProductTemplate(code="NO-BOM", name="Missing BOM", created_by="test")
    invalid = MesProductTemplate(code="BAD-BOM", name="Invalid BOM", created_by="test")
    db.add_all([missing, invalid]); db.flush()
    bad_route = MesProductionRoute(template_id=invalid.id, name="Bad route", version=1, is_default=True, created_by="test")
    db.add(bad_route); db.flush(); invalid.default_route_id = bad_route.id
    db.add(MesRouteStep(route_id=bad_route.id, stage_id=stage.id, step_order=1))
    db.add(MesBomLine(template_id=invalid.id, part_id=common.id, required_quantity=0, unit="dona"))
    db.add(WarehouseStock(detail_id=common.id, detail_code=common.part_number, detail_name=common.name, quantity=15, reserved_quantity=0, unit="dona", status="READY"))
    db.commit()
    ids = {"products": [p.id for p in products], "common": common.id, "missing": missing.id, "invalid": invalid.id}
    db.close(); return ids


def login(client, username, password):
    response = client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_project(client, headers, code="SI_UZ_Toshkent_Atlas_2026"):
    response = client.post("/production-projects", headers=headers, json={"project_code": code, "project_name": "Atlas project", "customer_name_snapshot": "Atlas Customer", "destination_region": "Toshkent", "destination_city": "Toshkent", "site_name": "Atlas shopping center", "full_address": "Toshkent", "required_delivery_date": "2026-09-25T00:00:00", "priority": "high"})
    assert response.status_code == 201, response.text
    return response.json()


def main():
    ids = setup_data(); client = TestClient(app)
    admin = login(client, "project-admin", "Project123!")
    viewer = login(client, "project-viewer", "Viewer123!")
    assert client.get("/production-projects", headers=viewer).status_code == 403
    project = create_project(client, admin); project_id = project["id"]
    assert client.post("/production-projects", headers=admin, json={"project_code": project["project_code"], "project_name": "Duplicate", "customer_name_snapshot": "Customer"}).status_code == 409

    for product_id in ids["products"]:
        response = client.post(f"/production-projects/{project_id}/lines", headers=admin, json={"product_id": product_id, "quantity": 1})
        assert response.status_code == 201, response.text
    project = client.get(f"/production-projects/{project_id}", headers=admin).json()
    assert len(project["lines"]) == 20

    duplicate = client.post(f"/production-projects/{project_id}/lines", headers=admin, json={"product_id": ids["products"][0], "quantity": 2})
    assert duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "duplicate_product_line"
    merged = client.post(f"/production-projects/{project_id}/lines/merge", headers=admin, json={"product_id": ids["products"][0], "additional_quantity": 2, "expected_project_version": project["version"]})
    assert merged.status_code == 200 and merged.json()["quantity"] == 3
    project = client.get(f"/production-projects/{project_id}", headers=admin).json()

    stale = client.put(f"/production-projects/{project_id}", headers=admin, json={"expected_version": project["version"] - 1, "notes": "stale"})
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "project_version_conflict"
    assert client.post(f"/production-projects/{project_id}/lines", headers=admin, json={"product_id": ids["products"][1], "quantity": 0}).status_code == 422

    preview = client.get(f"/production-projects/{project_id}/requirements/preview", headers=admin)
    assert preview.status_code == 200, preview.text
    body = preview.json(); shared = next(row for row in body["requirements"] if row["detail_id"] == ids["common"])
    assert shared["gross_required_quantity"] == 44
    shared_evidence = [row for row in body["evidence"] if row["detail_id"] == ids["common"]]
    assert len(shared_evidence) == 20 and sum(row["gross_quantity"] for row in shared_evidence) == 44

    planned = client.put(f"/production-projects/{project_id}", headers=admin, json={"expected_version": project["version"], "status": "planned"})
    assert planned.status_code == 200 and planned.json()["status"] == "planned"
    project = planned.json()

    missing_project = create_project(client, admin, "MISSING-BOM-PROJECT")
    assert client.post(f"/production-projects/{missing_project['id']}/lines", headers=admin, json={"product_id": ids["missing"], "quantity": 1}).status_code == 201
    missing_preview = client.get(f"/production-projects/{missing_project['id']}/requirements/preview", headers=admin)
    assert missing_preview.status_code == 409 and missing_preview.json()["detail"]["code"] == "missing_product_bom"

    invalid_project = create_project(client, admin, "INVALID-BOM-PROJECT")
    assert client.post(f"/production-projects/{invalid_project['id']}/lines", headers=admin, json={"product_id": ids["invalid"], "quantity": 1}).status_code == 201
    invalid_preview = client.get(f"/production-projects/{invalid_project['id']}/requirements/preview", headers=admin)
    assert invalid_preview.status_code == 409 and invalid_preview.json()["detail"]["code"] == "invalid_bom_quantity"

    release_key = "atlas-release-2026-revision-1"
    released = client.post(f"/production-projects/{project_id}/release", headers=admin, json={"expected_version": project["version"], "idempotency_key": release_key})
    assert released.status_code == 200, released.text
    release_body = released.json(); assert release_body["idempotent"] is False
    repeated = client.post(f"/production-projects/{project_id}/release", headers=admin, json={"expected_version": project["version"], "idempotency_key": release_key})
    assert repeated.status_code == 200 and repeated.json()["idempotent"] is True
    different = client.post(f"/production-projects/{project_id}/release", headers=admin, json={"expected_version": release_body["project"]["version"], "idempotency_key": "atlas-different-release-key"})
    assert different.status_code == 409

    db = SessionLocal()
    release = db.query(ProjectReleaseSnapshot).filter_by(project_id=project_id).one()
    assert release.checksum == body["checksum"]
    assert db.query(ProjectLineBomSnapshot).filter_by(release_id=release.id).count() == 40
    assert db.query(MesProductionJob).filter_by(project_id=project_id).count() == 20
    assert all(job.project_line_id and job.project_release_snapshot_id == release.id for job in db.query(MesProductionJob).filter_by(project_id=project_id))
    req = db.query(ProjectDetailRequirement).filter_by(release_id=release.id, detail_id=ids["common"]).one()
    assert req.gross_required_quantity == 44 and req.stock_reserved_quantity == 15 and req.production_required_quantity == 29
    allocation = db.query(ProjectStockAllocation).filter_by(requirement_id=req.id).one()
    stock = db.query(WarehouseStock).filter_by(id=allocation.stock_id).one()
    assert stock.quantity == 15 and stock.reserved_quantity == 15 and stock.reserved_quantity <= stock.quantity
    assert db.query(WarehouseTransaction).filter_by(operation="RESERVE", stock_id=stock.id).count() == 1
    allocation.consumed_quantity = 5; req.consumed_quantity = 5
    allocation_id, stock_id = allocation.id, allocation.stock_id
    db.commit(); db.close()

    cancelled = client.post(f"/production-projects/{project_id}/cancel", headers=admin, json={"expected_version": release_body["project"]["version"], "reason": "isolated test cancellation"})
    assert cancelled.status_code == 200, cancelled.text
    db = SessionLocal(); allocation = db.query(ProjectStockAllocation).filter_by(id=allocation_id).one(); stock = db.query(WarehouseStock).filter_by(id=stock_id).one()
    assert allocation.released_quantity == 10 and allocation.consumed_quantity == 5
    assert stock.reserved_quantity == 5
    assert db.query(AuditLog).filter_by(entity_type="production_project", entity_id=project_id).count() >= 4

    standalone = MesProductionJob(job_number="LEGACY-STANDALONE", customer_name="Legacy", template_id=ids["products"][1], quantity=1, status="draft", created_by="test")
    db.add(standalone); db.commit(); standalone_id = standalone.id; db.close()
    standalone_release = client.post(f"/mes/jobs/{standalone_id}/release", headers=admin)
    assert standalone_release.status_code == 200 and standalone_release.json()["project_id"] is None

    constraint_db = SessionLocal(); constraint_db.add(ProductionProjectLine(project_id=project_id, product_id=ids["missing"], quantity=0))
    try:
        constraint_db.commit(); raise AssertionError("positive quantity DB constraint did not fire")
    except IntegrityError:
        constraint_db.rollback()
    finally:
        constraint_db.close()
    print("test_production_projects: ALL TESTS PASSED (20 products, 44 shared demand, 15 reserved, 29 production required)")


if __name__ == "__main__":
    main()
