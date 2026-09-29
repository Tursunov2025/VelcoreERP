import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("JWT_SECRET_KEY", "test-material-cutting-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Material, MaterialIssue, MaterialScrap, MaterialStockLengthLot, MaterialStockMovement, MaterialStockPiece
from services.material_cutting import (create_issue_document, issue_reserved, materialize_lot,
    recommend, record_cut, release_reservation, reserve_piece)


def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def setup_stock(db):
    mat = Material(code="PR-RT-40X20X1.5", name="Profile", unit="m", material_type="PROFILE",
                   quantity=44, default_kerf_mm=3, min_reusable_offcut_m=.3)
    db.add(mat); db.flush()
    lots=[]
    for length, count in [(8,2),(10,2),(12,1)]:
        lot=MaterialStockLengthLot(material_id=mat.id,length_m=length,pieces_on_hand=count,
            pieces_reserved=0,total_meters=length*count,pieces_received=count,meters_received=length*count,
            warehouse_name="TEST",location_code="A1",created_by="tester")
        db.add(lot); db.flush(); materialize_lot(db,lot.id,"tester",f"materialize-{lot.id}"); lots.append(lot)
    db.commit(); return mat, lots


def make_issue(db, mat, qty, key):
    data={"material_id":mat.id,"quantity":qty,"operation_key":key,"job_id":1,
          "project_id":1,"project_line_id":1,"operation_stage":"LAZER"}
    create_issue_document(db,"operator",data); db.flush()
    return db.query(MaterialIssue).filter_by(operation_key=key).one()


def test_cut_offcut_reuse_balance_idempotency_and_scrap():
    db=db_session(); mat,_=setup_stock(db)
    first=recommend(db,mat.id,[2.35],.003); assert first["piece"]["current_length_m"]==8
    issue=make_issue(db,mat,2.35,"issue-first")
    reserve_piece(db,issue.id,first["piece"]["id"],first["piece"]["version"],"operator")
    issue_reserved(db,issue.id,"operator")
    result=record_cut(db,issue.id,first["piece"]["id"],2.35,.003,"cut-first","operator")
    cut=result["cuts"][0]; assert cut["remainder_m"]==5.647 and cut["offcut_piece_id"]
    assert abs(cut["length_before_m"]-cut["actual_cut_length_m"]-cut["kerf_m"]-cut["remainder_m"])<1e-9
    retry=record_cut(db,issue.id,first["piece"]["id"],2.35,.003,"cut-first","operator")
    assert retry["idempotent"] and len(retry["cuts"])==1

    second=recommend(db,mat.id,[3.10],.003); assert second["piece"]["id"]==cut["offcut_piece_id"]
    issue2=make_issue(db,mat,3.10,"issue-second")
    reserve_piece(db,issue2.id,second["piece"]["id"],second["piece"]["version"],"operator")
    issue_reserved(db,issue2.id,"operator")
    r2=record_cut(db,issue2.id,second["piece"]["id"],3.10,.003,"cut-second","operator")
    assert r2["cuts"][0]["remainder_m"]==2.544

    # Below threshold is recorded as scrap and is never an available piece.
    mat.min_reusable_offcut_m=3
    third=recommend(db,mat.id,[2.30],.003); issue3=make_issue(db,mat,2.30,"issue-third")
    reserve_piece(db,issue3.id,third["piece"]["id"],third["piece"]["version"],"operator"); issue_reserved(db,issue3.id,"operator")
    r3=record_cut(db,issue3.id,third["piece"]["id"],2.30,.003,"cut-third","operator")
    assert r3["cuts"][0]["scrap_length_m"]>0 and db.query(MaterialScrap).count()==1
    assert db.query(MaterialStockMovement).filter_by(reference_type="cut").count()==3


def test_reservation_conflict_release_and_multicut_plan():
    db=db_session(); mat,_=setup_stock(db)
    plan=recommend(db,mat.id,[2.35,3.10,1.75],.003)
    assert plan["piece"]["current_length_m"]==8 and plan["kerf_total_m"]==.009
    assert plan["remainder_m"]==.791
    a=make_issue(db,mat,2.35,"issue-a"); b=make_issue(db,mat,2.35,"issue-b"); b.job_id=2; db.commit(); p=plan["piece"]
    reserve_piece(db,a.id,p["id"],p["version"],"operator")
    try: reserve_piece(db,b.id,p["id"],p["version"],"operator"); assert False
    except ValueError as exc: assert exc.code=="material_piece_reservation_conflict"
    released=release_reservation(db,a.id,"operator"); assert released["status"]=="DRAFT"
    reserved=reserve_piece(db,b.id,p["id"],p["version"]+2,"operator")
    assert reserved["status"]=="RESERVED"


def test_partial_cut_can_continue_from_the_same_authoritative_issue():
    db=db_session(); mat,_=setup_stock(db)
    issue=make_issue(db,mat,3.0,"issue-partial")
    issue.planned_required_quantity=3.0; db.commit()
    first=recommend(db,mat.id,[1.0],.003)["piece"]
    reserve_piece(db,issue.id,first["id"],first["version"],"operator")
    issue_reserved(db,issue.id,"operator")
    partial=record_cut(db,issue.id,first["id"],1.0,.003,"cut-partial-a","operator")
    assert partial["status"]=="ISSUED"
    offcut=partial["cuts"][0]["offcut_piece_id"]
    offcut_row=db.get(MaterialStockPiece,offcut)
    reserve_piece(db,issue.id,offcut,offcut_row.version,"operator")
    issue_reserved(db,issue.id,"operator")
    done=record_cut(db,issue.id,offcut,2.0,.003,"cut-partial-b","operator")
    assert done["status"]=="COMPLETED" and len(done["cuts"])==2
    retry=record_cut(db,issue.id,offcut,2.0,.003,"cut-partial-b","operator")
    assert retry["idempotent"] and len(retry["cuts"])==2
