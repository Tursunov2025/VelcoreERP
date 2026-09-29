"""Isolated ProductionProject execution/progress regression tests."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TEST_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
TEST_ROOT = Path(tempfile.mkdtemp(prefix="velcore-project-execution-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{TEST_DB.replace(chr(92), '/')}", "DB_PATH": TEST_DB,
    "DATA_ROOT": str(TEST_ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
    "JWT_SECRET_KEY": "project-execution-test-secret",
})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (  # noqa: E402
    MesBomLine, MesJobPackage, MesProductionJob, MesProductionRoute, MesProductionStage,
    MesProductPart, MesProductTemplate, MesRouteStep, ProductionProject,
    ProjectProductionOperation, ProjectStockAllocation, User, UserPermission, WarehouseStock,
)
from auth.security import hash_password  # noqa: E402
from services.project_execution import ExecutionError, consume_project_stock, project_forecast, project_progress, record_absolute_operation  # noqa: E402


def main():
    Base.metadata.create_all(engine); run_migrations()
    db = SessionLocal()
    db.add_all([
        User(username="exec-admin", password_hash=hash_password("Exec123!"), role="admin", department="Admin"),
        User(username="exec-viewer", password_hash=hash_password("Viewer123!"), role="operator", department="Kesish"),
        User(username="terminal-only", password_hash=hash_password("Terminal123!"), role="operator", department="Kesish"),
        User(username="project-only", password_hash=hash_password("Project123!"), role="operator", department="Kesish"),
        User(username="authorized", password_hash=hash_password("Authorized123!"), role="operator", department="Kesish"),
    ])
    stage = MesProductionStage(name="Lazer", department="Kesish", is_active=True, is_system=True)
    part = MesProductPart(part_number="EXEC-PART", name="Execution part", created_by="test")
    product = MesProductTemplate(code="EXEC-PRODUCT", name="Execution product", created_by="test")
    db.add_all([stage, part, product]); db.flush()
    route = MesProductionRoute(template_id=product.id, name="Execution route", version=1, is_default=True, created_by="test")
    db.add(route); db.flush(); product.default_route_id = route.id
    db.add(MesRouteStep(route_id=route.id, stage_id=stage.id, step_order=1, department="Kesish"))
    db.add(MesBomLine(template_id=product.id, part_id=part.id, required_quantity=2, unit="dona"))
    db.add(WarehouseStock(detail_id=part.id, detail_code=part.part_number, detail_name=part.name, quantity=2, reserved_quantity=0, unit="dona", status="READY"))
    db.flush()
    users = {u.username: u for u in db.query(User).all()}
    db.add_all([
        UserPermission(user_id=users["terminal-only"].id, module="mes_terminal_lazer", enabled=True),
        UserPermission(user_id=users["project-only"].id, module="production_projects_execute", enabled=True),
        UserPermission(user_id=users["authorized"].id, module="mes_terminal_lazer", enabled=True),
        UserPermission(user_id=users["authorized"].id, module="production_projects_execute", enabled=True),
    ])
    db.commit(); product_id = product.id; part_id = part.id; db.close()

    client = TestClient(app)
    token = client.post("/auth/login", json={"username": "exec-admin", "password": "Exec123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    viewer_token = client.post("/auth/login", json={"username": "exec-viewer", "password": "Viewer123!"}).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    def auth(username, password):
        value = client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]
        return {"Authorization": f"Bearer {value}"}
    terminal_only = auth("terminal-only", "Terminal123!")
    project_only = auth("project-only", "Project123!")
    authorized = auth("authorized", "Authorized123!")
    created = client.post("/production-projects", headers=headers, json={
        "project_code": "EXEC-PROJECT", "project_name": "Execution project",
        "customer_name_snapshot": "Customer", "destination_city": "Toshkent", "site_name": "Site",
    }).json()
    assert client.post(f"/production-projects/{created['id']}/lines", headers=headers, json={"product_id": product_id, "quantity": 3}).status_code == 201
    current = client.get(f"/production-projects/{created['id']}", headers=headers).json()
    current = client.put(f"/production-projects/{created['id']}", headers=headers, json={"expected_version": current["version"], "status": "planned"}).json()
    released = client.post(f"/production-projects/{created['id']}/release", headers=headers, json={"expected_version": current["version"], "idempotency_key": "exec-release-1"})
    assert released.status_code == 200, released.text
    assert client.get(f"/production-projects/{created['id']}/forecast", headers=viewer_headers).status_code == 403

    db = SessionLocal(); released_job_id = db.query(MesProductionJob).filter_by(project_id=created["id"]).one().id; db.close()
    mutation_url = f"/mes/terminal/lazer/jobs/{released_job_id}/accept"
    assert client.post(mutation_url).status_code == 401
    assert client.post(mutation_url, headers=viewer_headers).status_code == 403
    denied = client.post(mutation_url, headers=terminal_only)
    assert denied.status_code == 403, denied.text
    assert client.post(mutation_url, headers=project_only).status_code == 403
    assert client.post(mutation_url, headers=headers).status_code == 200
    assert client.post(f"/mes/terminal/lazer/jobs/{released_job_id}/start", headers=authorized).status_code == 200

    db = SessionLocal(); project = db.query(ProductionProject).filter_by(id=created["id"]).one()
    job = db.query(MesProductionJob).filter_by(project_id=project.id).one(); line = job.bom_lines[0]
    assert line.stock_reserved_quantity == 2 and line.production_required_quantity == 4
    assert consume_project_stock(db, job, part_id, 1, "issuer") == 1
    allocation = db.query(ProjectStockAllocation).filter_by(project_id=project.id).one()
    assert allocation.consumed_quantity == 1
    stock = db.query(WarehouseStock).filter_by(id=allocation.stock_id).one()
    assert stock.quantity == 1 and stock.reserved_quantity == 1
    first = record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=2, username="operator", terminal="LAZER", job_line=line)
    assert first and first.quantity == 2
    assert record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=2, username="operator", terminal="LAZER", job_line=line) is first
    record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=4, username="operator", terminal="LAZER", job_line=line)
    try:
        record_absolute_operation(db, job, operation_type="lazer_completed", absolute_quantity=5, username="operator", terminal="LAZER", job_line=line)
        raise AssertionError("completion above production requirement was accepted")
    except ExecutionError as exc:
        assert exc.code == "quantity_exceeds_remaining"
    record_absolute_operation(db, job, operation_type="qc_approved", absolute_quantity=6, username="qc", terminal="QC", job_line=line)
    try:
        record_absolute_operation(db, job, operation_type="qc_rejected", absolute_quantity=1, username="qc", terminal="QC", job_line=line)
        raise AssertionError("QC beyond submitted quantity was accepted")
    except ExecutionError as exc:
        assert exc.code == "qc_exceeds_completed"
    job.packages.append(MesJobPackage(package_number="EXEC-PKG", package_type="box", quantity=3, status="packed", project_id=project.id, project_line_id=job.project_line_id, project_release_snapshot_id=job.project_release_snapshot_id))
    db.flush()
    record_absolute_operation(db, job, operation_type="packaged", absolute_quantity=2, username="packager", terminal="PACKAGING")
    progress = project_progress(db, project)
    # Project readiness is expressed in finished-product units: LAZER output
    # plus the reusable stock allocation, capped by the ordered quantity.
    assert progress["lines"][0]["produced_quantity"] == 3
    assert progress["lines"][0]["qc_approved_quantity"] == 3
    assert progress["lines"][0]["packaged_quantity"] == 2
    assert 0 < progress["overall_progress_percent"] < 100
    forecast = project_forecast(db, project)
    assert forecast["available"] is False and "forecast_insufficient_data" in forecast["reason_codes"]
    db.commit()
    assert db.query(ProjectProductionOperation).filter_by(project_id=project.id, operation_type="lazer_completed").count() == 2
    db.close()
    print("test_project_execution: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
