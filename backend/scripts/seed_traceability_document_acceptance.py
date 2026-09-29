"""Seed explicit disposable fixtures for Product Traceability document QA."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth.security import hash_password
from database import Base, SessionLocal, engine, run_migrations
from models import (
    MesDispatch, MesDispatchPackage, MesJobBomLine, MesJobPackage, MesJobRework,
    MesProductPart, MesProductTemplate, MesProductionJob, ProductPassport,
    ProductPassportSequence, User,
)
from services.package_traceability import product_passport_public_url


def main() -> None:
    Base.metadata.create_all(engine); run_migrations(); db = SessionLocal(); now = datetime.utcnow()
    try:
        admin = User(username="trace-doc-admin", password_hash=hash_password("TraceDoc123!"), role="admin", department="Admin")
        db.add(admin); db.flush()
        part = MesProductPart(part_number="TRACE-DOC-PART", name="Document QA detail", created_by=admin.username)
        db.add(part); db.flush()
        db.add(ProductPassportSequence(year=now.year, next_value=4))
        cases = [
            ("CLEAN", "Trace Clean Product", "received"),
            ("REWORK", "Trace QC Rework Product", "received"),
            ("SHIPPED", "Trace Shipped Product", "loaded"),
        ]
        for index, (code, name, package_status) in enumerate(cases, 1):
            template = MesProductTemplate(code=f"DOC-{code}", name=name, created_by=admin.username)
            db.add(template); db.flush()
            job = MesProductionJob(job_number=f"DOC-JOB-{index}", customer_name="TEST Atlas", template_id=template.id, quantity=1, status="completed", created_by=admin.username, started_at=now-timedelta(hours=3), completed_at=now-timedelta(hours=1))
            db.add(job); db.flush()
            bom = MesJobBomLine(job_id=job.id, part_id=part.id, part_number=part.part_number, part_name=part.name, allocated_quantity=1, completed_quantity=1, accepted_quantity=1, qc_accepted_quantity=1)
            package = MesJobPackage(job_id=job.id, package_number=f"DOC-PKG-{index}", quantity=1, status=package_status, net_weight_kg=18.5, gross_weight_kg=20.0, received_at=now-timedelta(minutes=50))
            db.add_all([bom, package]); db.flush()
            token = f"trace-doc-token-{index}"
            db.add(ProductPassport(serial_number=f"PRD-{now.year}-{index:06d}", qr_token=token, qr_data=product_passport_public_url(token), package_id=package.id, job_id=job.id, template_id=template.id, unit_index=1, unit_quantity=1, status=package_status, finalized_at=now, created_by=admin.username))
            if code == "REWORK":
                db.add(MesJobRework(job_id=job.id, bom_line_id=bom.id, quantity=1, status="completed", notes="TEST: QC weld correction", created_by=admin.username, created_at=now-timedelta(hours=2), started_at=now-timedelta(hours=2), completed_at=now-timedelta(hours=1,minutes=20), completed_by=admin.username))
            if code == "SHIPPED":
                dispatch = MesDispatch(dispatch_number="DOC-DISPATCH-1", job_id=job.id, customer_name="TEST Atlas", package_count=1, vehicle_number="TEST-01", driver_name="TEST Driver", status="shipped", ship_date=now-timedelta(minutes=30), destination_city="TEST Toshkent", site_name="TEST Atlas", created_by=admin.username)
                db.add(dispatch); db.flush(); db.add(MesDispatchPackage(dispatch_id=dispatch.id, package_id=package.id, status="shipped", loaded_by=admin.username, loaded_at=now-timedelta(minutes=45), shipped_at=now-timedelta(minutes=30)))
        db.commit()
        print("traceability document acceptance fixtures: 3 passports; login trace-doc-admin / TraceDoc123!")
    finally:
        db.close()


if __name__ == "__main__":
    main()
