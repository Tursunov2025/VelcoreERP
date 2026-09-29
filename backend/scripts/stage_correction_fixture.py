"""Explicit disposable-only fixtures for browser stage-correction acceptance."""
import os,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
db_path=Path(os.environ.get("DB_PATH","")).resolve()
if os.environ.get("ENVIRONMENT")!="test" or os.environ.get("DATABASE_GUARD","true").lower()!="false" or "material-cutting-linkage" not in str(db_path): raise SystemExit("refusing non-disposable database")
from database import SessionLocal
from models import MesJobBomLine,MesJobRouteStep,MesProductionJob,MesProductionStage,ProductionProject,ProductionProjectLine,ProjectLineBomSnapshot,ProjectProductionOperation,ProjectReleaseSnapshot,MesProductTemplate,MesBomLine
db=SessionLocal(); now=datetime.utcnow()
project=db.query(ProductionProject).filter_by(project_code="TEST-STAGE-CORRECTION").first()
if not project:
 template=db.query(MesProductTemplate).first(); source=db.query(MesBomLine).first()
 project=ProductionProject(project_code="TEST-STAGE-CORRECTION",project_name="TEST quantity-safe correction",customer_name_snapshot="TEST",status="in_production",created_by="admin");db.add(project);db.flush()
 line=ProductionProjectLine(project_id=project.id,product_id=template.id,quantity=10,status="in_production");db.add(line);db.flush()
 release=ProjectReleaseSnapshot(project_id=project.id,revision=1,source_project_version=1,idempotency_key="test-stage-correction-release",checksum="test",released_by="admin");db.add(release);db.flush()
 snap=ProjectLineBomSnapshot(release_id=release.id,project_line_id=line.id,product_id=template.id,source_bom_line_id=source.id,detail_id=source.part_id,product_code=template.code,product_name=template.name,detail_code=source.part.part_number,detail_name=source.part.name,unit="dona",source_quantity=1,product_quantity=10,gross_quantity=10);db.add(snap);db.flush()
 stages={}
 for order,name in enumerate(["LAZER","SVARKA","Kraska","QC"],1):
  stage=db.query(MesProductionStage).filter(MesProductionStage.name.ilike(name)).first()
  if not stage: stage=MesProductionStage(name=name,department=name,sort_order=order,is_active=True);db.add(stage);db.flush()
  stages[name]=stage
 for suffix,reconcile in [("RETURN",False),("RECONCILE",True)]:
  job=MesProductionJob(job_number=f"TEST-STAGE-{suffix}",template_id=template.id,quantity=10,status="in_progress",created_by="admin",project_id=project.id,project_line_id=line.id,project_release_snapshot_id=release.id);db.add(job);db.flush()
  jl=MesJobBomLine(job_id=job.id,source_bom_line_id=source.id,part_id=source.part_id,part_number=source.part.part_number,part_name=source.part.name,unit="dona",allocated_quantity=10,production_required_quantity=10,completed_quantity=10,accepted_quantity=10,painted_quantity=10,paint_accepted_quantity=0 if reconcile else 10,qc_accepted_quantity=0 if reconcile else 7,qc_rework_quantity=0 if reconcile else 3,project_line_bom_snapshot_id=snap.id);db.add(jl);db.flush()
  for order,name in enumerate(["LAZER","SVARKA","Kraska","QC"],1): db.add(MesJobRouteStep(job_id=job.id,stage_id=stages[name].id,stage_name=name,step_order=order,accepted_at=now,started_at=now,completed_at=now if name!="QC" else None))
  for kind,qty in [("lazer_completed",10),("svarka_accepted",10),("painting_completed",10)]+([] if reconcile else [("painting_accepted",10),("qc_approved",7),("rework_created",3)]): db.add(ProjectProductionOperation(project_id=project.id,release_id=release.id,project_line_id=line.id,job_id=job.id,job_line_id=jl.id,operation_type=kind,quantity=qty,accepted_quantity=qty if "accepted" in kind or kind=="qc_approved" else 0,rework_quantity=qty if kind=="rework_created" else 0,operator="admin",terminal="test_fixture",source_record_type="test_fixture",source_record_id=jl.id,source_version=kind,idempotency_key=f"test-{suffix}-{kind}"))
 db.commit()
print({"project_id":project.id,"jobs":[(j.id,j.job_number) for j in db.query(MesProductionJob).filter(MesProductionJob.job_number.like("TEST-STAGE-%")).all()]})
