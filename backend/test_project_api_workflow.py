"""Project-linked API success path through every shipping stage (isolated SQLite)."""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path

DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(tempfile.mkdtemp(prefix="velcore-project-api-"))
os.environ.update({"DATABASE_URL": f"sqlite:///{DB.replace(chr(92), '/')}", "DB_PATH": DB,
                   "DATA_ROOT": str(ROOT), "DATABASE_GUARD": "false", "ENVIRONMENT": "test",
                   "JWT_SECRET_KEY": "project-api-workflow-secret"})
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi.testclient import TestClient  # noqa: E402
from database import Base, SessionLocal, engine, run_migrations  # noqa: E402
from main import app  # noqa: E402
from models import (AuditLog, MesBomLine, MesDispatch, MesDispatchPackage, MesFinishedGoodsInventory, MesInventoryMovement, MesJobBomLine, MesJobPackage,
                    MesProductionJob, MesProductionRoute, MesProductionStage, MesProductCategory,
                    MesProductPart, MesProductTemplate, MesRouteStep, MesWarehouseLocation,
                    ProductionProject, ProjectProductionOperation, User)  # noqa: E402
from services.seed import seed_defaults  # noqa: E402
from services.project_execution import record_absolute_operation  # noqa: E402
from services.qc_predecessor_reconciliation import reconcile_qc_predecessors  # noqa: E402


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def main():
    Base.metadata.create_all(engine); run_migrations(); db = SessionLocal(); seed_defaults(db)
    category = MesProductCategory(name="Project API", created_by="admin")
    part = MesProductPart(part_number="PRJ-API-PART", name="Project part", unit="dona", created_by="admin")
    template = MesProductTemplate(code="PRJ-API-PRODUCT", name="Project product", created_by="admin")
    db.add_all([category, part, template]); db.flush(); template.category_id = category.id
    other_template = MesProductTemplate(category_id=category.id, code="PRJ-API-OTHER", name="Other product", created_by="admin")
    db.add(other_template); db.flush(); other_template_id = other_template.id
    db.add(MesBomLine(template_id=template.id, part_id=part.id, required_quantity=2, is_active=True))
    route = MesProductionRoute(template_id=template.id, name="Project full route", version=1, is_default=True, is_active=True, created_by="admin")
    db.add(route); db.flush(); template.default_route_id = route.id
    names = ["Lazer", "Svarshik", "Kraska", "Nazorat", "Upakovka", "Sklad", "Yuklash"]
    stages = {s.name: s for s in db.query(MesProductionStage).filter(MesProductionStage.name.in_(names)).all()}
    assert set(names) == set(stages), stages.keys()
    for order, name in enumerate(names): db.add(MesRouteStep(route_id=route.id, stage_id=stages[name].id, step_order=order, is_required=True))
    db.commit(); template_id = template.id

    client = TestClient(app); token = ok(client.post("/auth/login", json={"username": "admin", "password": "1234"}))["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/production-projects", headers=headers, json={"project_code": "project_api_success", "project_name": "API workflow", "customer_name_snapshot": "Atlas", "destination_city": "Toshkent", "site_name": "Atlas"})
    assert project.status_code == 201, project.text; project = project.json(); pid = project["id"]
    project_b = client.post("/production-projects", headers=headers, json={"project_code": "test_samarqand_sentrium", "project_name": "Sentrium", "customer_name_snapshot": "B", "destination_city": "Samarqand", "site_name": "Sentrium"}).json()
    project_c = client.post("/production-projects", headers=headers, json={"project_code": "test_toshkent_other", "project_name": "Other site", "customer_name_snapshot": "C", "destination_city": "Toshkent", "site_name": "Other"}).json()
    assert client.post(f"/production-projects/{project_b['id']}/lines", headers=headers, json={"product_id": template_id, "quantity": 1}).status_code == 201
    project_b = ok(client.get(f"/production-projects/{project_b['id']}", headers=headers))
    project_b = ok(client.put(f"/production-projects/{project_b['id']}", headers=headers, json={"expected_version": project_b["version"], "status": "planned"}))
    ok(client.post(f"/production-projects/{project_b['id']}/release", headers=headers, json={"expected_version": project_b["version"], "idempotency_key": "project-b-release"}))
    db.expire_all(); b_job = db.query(MesProductionJob).filter_by(project_id=project_b["id"]).one(); b_line_id = b_job.project_line_id; b_release_id = b_job.project_release_snapshot_id
    assert client.post(f"/production-projects/{pid}/lines", headers=headers, json={"product_id": template_id, "quantity": 3}).status_code == 201
    project = ok(client.get(f"/production-projects/{pid}", headers=headers))
    project = ok(client.put(f"/production-projects/{pid}", headers=headers, json={"expected_version": project["version"], "status": "planned"}))
    release = ok(client.post(f"/production-projects/{pid}/release", headers=headers, json={"expected_version": project["version"], "idempotency_key": "project-api-release"}))
    assert ok(client.get(f"/production-projects/{pid}/forecast", headers=headers))["available"] is False
    db.expire_all(); job = db.query(MesProductionJob).filter_by(project_id=pid).one(); line = job.bom_lines[0]; jid, lid = job.id, line.id

    ok(client.post(f"/mes/terminal/lazer/jobs/{jid}/accept", headers=headers)); ok(client.post(f"/mes/terminal/lazer/jobs/{jid}/start", headers=headers))
    ok(client.put(f"/mes/terminal/lazer/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "completed_quantity": 3}]}))
    ok(client.put(f"/mes/terminal/lazer/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "completed_quantity": 6}]}))
    ok(client.post(f"/mes/terminal/svarshik/jobs/{jid}/accept", headers=headers)); ok(client.post(f"/mes/terminal/svarshik/jobs/{jid}/start", headers=headers))
    ok(client.put(f"/mes/terminal/svarshik/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "completed_quantity": 6, "accepted_quantity": 6, "rejected_quantity": 0}]}))
    ok(client.post(f"/mes/terminal/kraska/jobs/{jid}/accept", headers=headers)); ok(client.post(f"/mes/terminal/kraska/jobs/{jid}/start", headers=headers))
    ok(client.put(f"/mes/terminal/kraska/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "painted_quantity": 6, "accepted_quantity": 6, "rejected_quantity": 0}]}))
    ok(client.post(f"/mes/terminal/qc/jobs/{jid}/accept", headers=headers)); ok(client.post(f"/mes/terminal/qc/jobs/{jid}/start", headers=headers))
    # QC uses authoritative Painting BOM completion even if legacy operation
    # evidence is missing. Zero completion rejects; partial completion succeeds;
    # retries are absolute/idempotent and the full disposition invariant holds.
    db.query(ProjectProductionOperation).filter_by(job_line_id=lid, operation_type="painting_accepted").delete()
    db.expire_all(); line = db.get(MesJobBomLine, lid)
    line.paint_accepted_quantity = 0; db.commit()
    db.add(ProjectProductionOperation(project_id=project_b["id"], release_id=b_release_id,
        project_line_id=b_line_id, job_id=jid, job_line_id=lid, operation_type="painting_accepted",
        quantity=6, accepted_quantity=6, operator="mismatch", terminal="test",
        source_record_type="mismatched_test", source_record_id=lid, source_version="6",
        idempotency_key=f"mismatched-paint-{lid}")); db.commit()
    operations_before = db.query(ProjectProductionOperation).count(); audits_before = db.query(AuditLog).count()
    read_only = ok(client.get(f"/mes/terminal/qc/jobs/{jid}", headers=headers))["qc_parts"][0]
    assert read_only["completed_before_qc"] == 0
    assert read_only["qc_diagnostic_code"] == "QC-RECONCILE-PAINT-ACCEPTANCE"
    assert db.query(ProjectProductionOperation).count() == operations_before and db.query(AuditLog).count() == audits_before
    blocked = client.put(f"/mes/terminal/qc/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "accepted_quantity": 2}]})
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "qc_exceeds_completed", blocked.text
    db.expire_all(); line = db.get(MesJobBomLine, lid)
    assert line.qc_accepted_quantity == 0
    dry = reconcile_qc_predecessors(db, job_id=jid, dry_run=True, actor="test")
    assert dry["eligible"] == 1 and dry["applied"] == 0
    applied = reconcile_qc_predecessors(db, job_id=jid, dry_run=False, actor="test"); db.commit()
    assert applied["applied"] == 1
    repeated = reconcile_qc_predecessors(db, job_id=jid, dry_run=False, actor="test"); db.commit()
    assert repeated["applied"] == 0 and repeated["eligible"] == 0
    partial = ok(client.put(f"/mes/terminal/qc/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "accepted_quantity": 2}]}))
    assert partial["qc_parts"][0]["completed_before_qc"] == 6 and partial["qc_parts"][0]["available_for_qc"] == 4
    ok(client.put(f"/mes/terminal/qc/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "accepted_quantity": 2}]}))
    assert db.query(ProjectProductionOperation).filter_by(job_line_id=lid, operation_type="qc_approved").count() == 1
    excessive = client.put(f"/mes/terminal/qc/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "accepted_quantity": 6, "rejected_quantity": 1}]})
    assert excessive.status_code == 409 and excessive.json()["detail"]["code"] == "qc_exceeds_completed"
    db.expire_all(); line = db.query(MesProductionJob).filter_by(id=jid).one().bom_lines[0]
    assert line.qc_accepted_quantity == 2 and line.qc_rejected_quantity == 0
    ok(client.put(f"/mes/terminal/qc/jobs/{jid}/quantities", headers=headers, json={"lines": [{"bom_line_id": lid, "accepted_quantity": 6, "rejected_quantity": 0, "rework_quantity": 0}]}))
    ok(client.post(f"/mes/terminal/packaging/jobs/{jid}/accept", headers=headers)); ok(client.post(f"/mes/terminal/packaging/jobs/{jid}/start", headers=headers))
    packaged = ok(client.put(f"/mes/terminal/packaging/jobs/{jid}/packaging-data", headers=headers, json={"package_type": "box", "package_count": 1, "packaged_quantity": 3}))
    package_id = packaged["packages"][0]["id"]; ok(client.post(f"/mes/terminal/packaging/jobs/{jid}/complete", headers=headers))
    location = db.query(MesWarehouseLocation).filter_by(code="A-01-01").one()
    ok(client.post(f"/mes/terminal/warehouse/jobs/{jid}/accept", headers=headers)); ok(client.post(f"/mes/terminal/warehouse/jobs/{jid}/start", headers=headers))
    ok(client.post(f"/mes/terminal/warehouse/jobs/{jid}/packages/{package_id}/place", headers=headers, json={"location_id": location.id}))
    ok(client.post(f"/mes/terminal/warehouse/jobs/{jid}/complete", headers=headers))
    ok(client.post(f"/mes/terminal/dispatch/jobs/{jid}/accept", headers=headers)); ok(client.post(f"/mes/terminal/dispatch/jobs/{jid}/start", headers=headers))
    ok(client.put(f"/mes/terminal/dispatch/jobs/{jid}/transport", headers=headers, json={"vehicle_number": "01A001AA"}))

    # Every mismatch is rejected before load state, movement, audit, or lifecycle changes.
    db.expire_all(); pkg = db.query(MesJobPackage).filter_by(id=package_id).one(); inv = db.query(MesFinishedGoodsInventory).filter_by(package_id=package_id).one(); dispatch = db.query(MesDispatch).filter_by(job_id=jid).one()
    baseline_movements = db.query(MesInventoryMovement).count(); baseline_audits = db.query(AuditLog).count()
    original = {"project_id": pkg.project_id, "line": pkg.project_line_id, "release": pkg.project_release_snapshot_id,
                "template": inv.template_id, "city": dispatch.destination_city, "site": dispatch.site_name}
    cases = [
        (pkg, "project_id", project_b["id"]),
        (pkg, "project_line_id", b_line_id),
        (pkg, "project_release_snapshot_id", b_release_id),
        (inv, "template_id", other_template_id),
        (dispatch, "destination_city", "Samarqand"),
        (dispatch, "site_name", project_c["site_name"]),
    ]
    for target, field, wrong in cases:
        prior = getattr(target, field); setattr(target, field, wrong); db.commit()
        rejected = client.post(f"/mes/terminal/dispatch/jobs/{jid}/packages/{package_id}/load", headers=headers)
        assert rejected.status_code == 409 and rejected.json()["detail"]["code"] == "dispatch_package_mismatch", rejected.text
        db.expire_all(); dp = db.query(MesDispatchPackage).filter_by(package_id=package_id).one()
        assert dp.status == "pending" and db.query(MesInventoryMovement).count() == baseline_movements
        assert db.query(AuditLog).count() == baseline_audits
        assert db.query(ProductionProject).filter_by(id=pid).one().status != "shipped"
        target = db.get(type(target), target.id); setattr(target, field, prior); db.commit()
    ok(client.post(f"/mes/terminal/dispatch/jobs/{jid}/packages/{package_id}/load", headers=headers))
    shipped = ok(client.post(f"/mes/terminal/dispatch/jobs/{jid}/ship", headers=headers))
    assert shipped["dispatch"]["status"] == "shipped"
    db.expire_all(); project = db.query(ProductionProject).filter_by(id=pid).one()
    assert project.status == "shipped"; assert project.lines[0].shipped_quantity == 3
    operations = db.query(ProjectProductionOperation).filter_by(project_id=pid).all()
    assert {o.operation_type for o in operations} >= {"lazer_completed", "svarka_accepted", "painting_accepted", "qc_approved", "packaged"}
    assert all(o.project_line_id and o.release_id and o.job_id == jid for o in operations)
    assert db.query(AuditLog).count() > 0
    retry = client.post(f"/mes/terminal/dispatch/jobs/{jid}/ship", headers=headers)
    assert retry.status_code in (400, 409)
    db.expire_all(); assert db.query(ProductionProject).filter_by(id=pid).one().status == "shipped"
    print("test_project_api_workflow: ALL TESTS PASSED")


if __name__ == "__main__": main()
