import os,sys
from datetime import datetime
from pathlib import Path
os.environ.setdefault("DATABASE_URL","sqlite:///:memory:");sys.path.insert(0,str(Path(__file__).parent))
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base,MesFinishedGoodsInventory,MesJobBomLine,MesJobPackage,MesJobRouteStep,MesProductionJob,ProductionProject,ProductionProjectLine,ProjectProductionOperation,ProjectReleaseSnapshot
from services.stage_corrections import StageCorrectionError,reopen_stage,return_stage

def setup():
 e=create_engine("sqlite:///:memory:");Base.metadata.create_all(e);db=sessionmaker(bind=e)()
 p=ProductionProject(project_code="RET-1",project_name="Return",customer_name_snapshot="TEST",status="in_production",created_by="admin")
 db.add(p);db.flush();pl=ProductionProjectLine(project_id=p.id,product_id=1,quantity=10,status="in_production");db.add(pl);db.flush()
 rel=ProjectReleaseSnapshot(project_id=p.id,revision=1,source_project_version=1,idempotency_key="release-return",checksum="x",released_by="admin");db.add(rel);db.flush()
 j=MesProductionJob(job_number="RET-JOB",template_id=1,quantity=10,status="completed",created_by="admin",project_id=p.id,project_line_id=pl.id,project_release_snapshot_id=rel.id)
 db.add(j);db.flush();line=MesJobBomLine(job_id=j.id,part_id=1,part_number="D1",part_name="Detail",allocated_quantity=10,production_required_quantity=10,completed_quantity=10,painted_quantity=10,paint_accepted_quantity=10,accepted_quantity=10,qc_accepted_quantity=7,qc_rework_quantity=3)
 db.add(line);db.flush();step=MesJobRouteStep(job_id=j.id,stage_id=1,stage_name="Kraska",step_order=1,completed_at=datetime.utcnow());db.add(step)
 for kind,qty in [("lazer_completed",10),("svarka_accepted",10),("painting_completed",10),("painting_accepted",10),("qc_approved",7),("rework_created",3)]: db.add(ProjectProductionOperation(project_id=p.id,release_id=rel.id,project_line_id=pl.id,job_id=j.id,job_line_id=line.id,operation_type=kind,quantity=qty,operator="admin",source_record_type="test",source_record_id=line.id,source_version=kind,idempotency_key=f"seed-{kind}"))
 db.commit();return db,p,pl,j,line,step

def test_partial_return_retry_and_status_recalculation():
 db,p,pl,j,line,_=setup();a=return_stage(db,job_id=j.id,job_line_id=line.id,source_stage="qc",destination_stage="painting",quantity=3,reason_code="repaint",comment="TEST",operation_key="return-operation-1",actor="admin");db.commit()
 assert not a["idempotent"] and line.qc_accepted_quantity==7 and line.qc_rework_quantity==0
 assert db.query(ProjectProductionOperation).filter_by(operation_type="qc_return_to_painting").count()==1
 b=return_stage(db,job_id=j.id,job_line_id=line.id,source_stage="qc",destination_stage="painting",quantity=3,reason_code="repaint",comment="TEST",operation_key="return-operation-1",actor="admin")
 assert b["idempotent"] and db.query(ProjectProductionOperation).filter_by(operation_type="qc_return_to_painting").count()==1
 assert p.status=="in_production" and pl.status=="in_production"

def test_downstream_blocks_return_and_reopen():
 db,_,_,j,line,step=setup();pkg=MesJobPackage(job_id=j.id,package_number="PK-LOCK",quantity=1,status="completed",project_id=j.project_id,project_line_id=j.project_line_id,project_release_snapshot_id=j.project_release_snapshot_id);db.add(pkg);db.commit()
 for call in (lambda:return_stage(db,job_id=j.id,job_line_id=line.id,source_stage="qc",destination_stage="painting",quantity=1,reason_code="repaint",comment="",operation_key="blocked-return",actor="admin"),lambda:reopen_stage(db,job_id=j.id,stage="kraska",reason_code="incorrect_completion",comment="",operation_key="blocked-reopen",actor="admin")):
  try: call();assert False
  except StageCorrectionError as exc: assert "downstream_locked" in exc.code
 assert step.completed_at is not None

def test_reopen_preserves_original_completion_and_is_idempotent():
 db,_,_,j,_,step=setup();original=step.completed_at;a=reopen_stage(db,job_id=j.id,stage="kraska",reason_code="incorrect_completion",comment="TEST",operation_key="reopen-operation-1",actor="admin");db.commit()
 assert not a["idempotent"] and step.completed_at is None
 event=db.get(ProjectProductionOperation,a["id"]);assert event.original_completed_at==original and event.reopened_by=="admin"
 b=reopen_stage(db,job_id=j.id,stage="kraska",reason_code="incorrect_completion",comment="TEST",operation_key="reopen-operation-1",actor="admin")
 assert b["idempotent"] and db.query(ProjectProductionOperation).filter_by(operation_type="stage_reopened").count()==1
