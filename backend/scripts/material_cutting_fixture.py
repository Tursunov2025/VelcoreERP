"""Explicit disposable Project→BOM→cutting acceptance fixture."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if os.getenv("ENVIRONMENT", "").lower() != "test" or os.getenv("DATABASE_GUARD", "").lower() != "false":
    raise RuntimeError("Fixture requires ENVIRONMENT=test and DATABASE_GUARD=false")
db_path = Path(os.environ["DB_PATH"]).resolve()
if "azmuserp" in str(db_path).lower() or "material-cutting-linkage" not in str(db_path).lower():
    raise RuntimeError(f"Refusing non-disposable database: {db_path}")

from database import Base, SessionLocal, engine, run_migrations
from models import (Material, MaterialBomLine, MaterialStockLengthLot, MesBomLine,
    MesProductionJob, MesProductionRoute, MesProductionStage, MesProductPart, MesProductTemplate,
    MesRouteStep, ProductionProject, ProductionProjectLine)
from services.material_cutting import materialize_lot
from services.production_projects import release_project
from services.seed import seed_defaults

Base.metadata.create_all(engine); run_migrations()
db=SessionLocal(); seed_defaults(db)
existing=db.query(ProductionProject).filter_by(project_code="TEST-CUT-PROJECT").first()
if existing:
    print({"project_id":existing.id,"status":existing.status,"reused":True}); db.close(); raise SystemExit(0)
mat=Material(code="PR-RT-40X20X1.5",name="TEST 40x20 profile",unit="m",purchase_unit="dona",
    material_type="PROFILE",profile_type="RECTANGULAR",width_mm=40,height_mm=20,thickness_mm=1.5,
    quantity=8,min_reusable_offcut_m=.3,default_kerf_mm=3,is_active=True)
part=MesProductPart(part_number="TEST-CUT-DETAIL",name="TEST cut detail",unit="dona",created_by="fixture")
product=MesProductTemplate(code="TEST-CUT-PRODUCT",name="TEST cut product",created_by="fixture")
stage=db.query(MesProductionStage).filter_by(name="Lazer").first()
if not stage: stage=MesProductionStage(name="Lazer",department="Kesish",is_active=True,is_system=True)
db.add_all([mat,part,product,stage]); db.flush()
route=MesProductionRoute(template_id=product.id,name="TEST cutting route",version=1,is_default=True,is_active=True,created_by="fixture")
db.add(route); db.flush(); product.default_route_id=route.id
db.add(MesRouteStep(route_id=route.id,stage_id=stage.id,step_order=1,department="Kesish",is_required=True))
db.add(MesBomLine(template_id=product.id,part_id=part.id,required_quantity=1,unit="dona",sort_order=1,is_active=True))
db.add(MaterialBomLine(part_id=part.id,material_id=mat.id,quantity_per_part=2.35,is_active=True))
lot=MaterialStockLengthLot(material_id=mat.id,length_m=8,pieces_on_hand=1,pieces_reserved=0,total_meters=8,
    pieces_received=1,meters_received=8,status="ACTIVE",warehouse_name="TEST",location_code="CUT-A1",
    lot_number="TEST-CUT-8M",created_by="fixture")
project=ProductionProject(project_code="TEST-CUT-PROJECT",project_name="TEST cutting linkage",
    customer_name_snapshot="TEST",destination_city="TEST",site_name="TEST",priority="normal",
    status="planned",version=1,created_by="fixture")
db.add_all([lot,project]); db.flush()
line=ProductionProjectLine(project_id=project.id,product_id=product.id,quantity=1,line_reference="TEST-CUT-LINE")
db.add(line); db.flush(); materialize_lot(db,lot.id,"fixture",f"fixture-lot-{lot.id}"); db.commit()
project,snapshot,_=release_project(db,project.id,project.version,"test-cut-release-1","fixture")
db.commit(); db.refresh(project)
job=db.query(MesProductionJob).filter_by(project_id=project.id).one()
print({"project_id":project.id,"project_line_id":line.id,"release_snapshot_id":snapshot.id,
       "job_id":job.id,"material_id":mat.id,"piece_count":1,"db":str(db_path)})
db.close()
