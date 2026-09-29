"""Focused Phase 3 authoritative logistics planning acceptance."""
import os, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path

DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
ROOT = Path(tempfile.mkdtemp(prefix="velcore-logistics-phase3-"))
os.environ.update({"DATABASE_URL":f"sqlite:///{DB.replace(chr(92), '/')}","DB_PATH":DB,"DATA_ROOT":str(ROOT),"DATABASE_GUARD":"false","ENVIRONMENT":"test","JWT_SECRET_KEY":"phase3-test-secret"})
sys.path.insert(0,str(Path(__file__).resolve().parent))

from database import Base, SessionLocal, engine, run_migrations
from fastapi.testclient import TestClient
from auth.security import hash_password
from main import app
from models import MesTrip, MesTripLatestLocation, MesTripLocation, MesTripTrackingSession, MesVehicle, ProductionProject, ProjectReleaseSnapshot, User
from services.logistics_planning import LogisticsPlanningError, derive_trip_alerts, sla_state, update_trip_assignment, update_trip_plan, update_vehicle_state
from migrations.production_projects import _column_ddl


def expect(code, fn):
    try: fn(); raise AssertionError(f"expected {code}")
    except LogisticsPlanningError as exc: assert exc.code == code


def test_phase3_assignment_planning_state_and_alerts():
    assert _column_ddl("postgresql", "DATETIME") == "TIMESTAMP WITHOUT TIME ZONE"
    Base.metadata.create_all(engine); run_migrations(); db=SessionLocal()
    project=ProductionProject(project_code="P3",project_name="P3",customer_name_snapshot="T",destination_city="Toshkent",site_name="Atlas",full_address="Test",status="released",release_revision=1,created_by="test")
    admin=User(username="phase3-admin",password_hash=hash_password("Phase3Admin123!"),role="admin",department="Admin",is_active=True)
    d1=User(username="phase3-driver-1",password_hash="x",role="driver",department="Logistika",is_active=True)
    d2=User(username="phase3-driver-2",password_hash="x",role="driver",department="Logistika",is_active=True)
    v1=MesVehicle(vehicle_type="truck",registration_number="P3-1",max_payload_kg=1000,internal_length_mm=4000,internal_width_mm=2000,internal_height_mm=2000,is_active=True,operational_state="AVAILABLE",created_by="test",updated_by="test")
    v2=MesVehicle(vehicle_type="truck",registration_number="P3-2",max_payload_kg=1000,internal_length_mm=4000,internal_width_mm=2000,internal_height_mm=2000,is_active=True,operational_state="AVAILABLE",created_by="test",updated_by="test")
    db.add_all([project,admin,d1,d2,v1,v2]);db.flush()
    release=ProjectReleaseSnapshot(project_id=project.id,revision=1,source_project_version=1,idempotency_key="phase3-release",checksum="0"*64,released_by="test");db.add(release);db.flush()
    t1=MesTrip(trip_number="P3-T1",vehicle_id=v1.id,driver_user_id=d1.id,project_id=project.id,release_id=release.id,destination_city="Toshkent",destination_site="Atlas",destination_address="Test",status="planned",created_by="test",updated_by="test")
    t2=MesTrip(trip_number="P3-T2",vehicle_id=v2.id,driver_user_id=d2.id,project_id=project.id,release_id=release.id,destination_city="Toshkent",destination_site="Atlas",destination_address="Test",status="planned",created_by="test",updated_by="test")
    db.add_all([t1,t2]);db.commit()
    expect("vehicle_assignment_conflict",lambda:update_trip_assignment(db,t2.id,vehicle_id=v1.id,driver_user_id=d2.id,expected_version=t2.version,actor="test"));db.rollback()
    expect("driver_assignment_conflict",lambda:update_trip_assignment(db,t2.id,vehicle_id=v2.id,driver_user_id=d1.id,expected_version=t2.version,actor="test"));db.rollback()
    client=TestClient(app);token=client.post("/auth/login",json={"username":"phase3-admin","password":"Phase3Admin123!"}).json()["access_token"]
    response=client.put(f"/mes/finished-logistics/trips/{t2.id}/assignment",headers={"Authorization":f"Bearer {token}"},json={"expected_version":t2.version,"vehicle_id":v1.id,"driver_user_id":d2.id})
    assert response.status_code==409 and response.json()["detail"]["code"]=="vehicle_assignment_conflict"
    t1=db.get(MesTrip,t1.id);t1.status="accepted";db.commit();t2=db.get(MesTrip,t2.id)
    update_trip_assignment(db,t2.id,vehicle_id=v1.id,driver_user_id=d1.id,expected_version=t2.version,actor="test");db.commit()
    t2=db.get(MesTrip,t2.id);expect("trip_version_conflict",lambda:update_trip_assignment(db,t2.id,vehicle_id=v2.id,driver_user_id=d2.id,expected_version=t2.version-1,actor="test"));db.rollback()
    now=datetime.utcnow();t2=db.get(MesTrip,t2.id)
    expect("departure_before_loading",lambda:update_trip_plan(db,t2.id,planned_loading_at=now,planned_departure_at=now-timedelta(hours=1),delivery_deadline_at=now+timedelta(hours=1),expected_version=t2.version,actor="test"));db.rollback()
    t2=db.get(MesTrip,t2.id);update_trip_plan(db,t2.id,planned_loading_at=now,planned_departure_at=now+timedelta(hours=1),delivery_deadline_at=now+timedelta(hours=2),expected_version=t2.version,actor="test");db.commit()
    t2=db.get(MesTrip,t2.id);assert sla_state(t2,now)=="on_schedule";t2.delivery_deadline_at=None;assert sla_state(t2,now)=="deadline_unavailable";t2.delivery_deadline_at=now-timedelta(minutes=1);db.commit();assert sla_state(t2,now)=="delayed"
    assert {x["type"] for x in derive_trip_alerts(db,t2,now)}=={"TRIP_DELAYED","VEHICLE_WITH_ACTIVE_TRIP_NO_GPS"}
    t2.arrived_at=now;assert sla_state(t2,now)=="delivered_late";t2.arrived_at=now-timedelta(minutes=3);t2.delivery_deadline_at=now-timedelta(minutes=2);assert sla_state(t2,now)=="delivered_on_time";t2.arrived_at=None;db.commit()
    session=MesTripTrackingSession(trip_id=t2.id,vehicle_id=v1.id,driver_user_id=d1.id,client_session_id="phase3-alert-session",status="active",last_contact_at=now,health_state="offline")
    db.add(session);db.flush();point=MesTripLocation(session_id=session.id,trip_id=t2.id,vehicle_id=v1.id,driver_user_id=d1.id,client_point_id="phase3-alert-point",payload_hash="1"*64,latitude=41,longitude=69,captured_at=now,received_at=now);db.add(point);db.flush();db.add(MesTripLatestLocation(trip_id=t2.id,session_id=session.id,vehicle_id=v1.id,driver_user_id=d1.id,location_id=point.id,latitude=41,longitude=69,captured_at=now,received_at=now));db.commit()
    assert "GPS_OFFLINE" in {x["type"] for x in derive_trip_alerts(db,t2,now)}
    session=db.get(MesTripTrackingSession,session.id);session.health_state="active";session.last_contact_at=now-timedelta(hours=1);db.commit();assert "GPS_STALE_SIGNAL" in {x["type"] for x in derive_trip_alerts(db,t2,now)}
    expect("vehicle_active_trip_conflict",lambda:update_vehicle_state(db,v1.id,operational_state="SERVICE",expected_version=db.get(MesVehicle,v1.id).version,actor="test"));db.rollback()
    t2=db.get(MesTrip,t2.id);t2.status="accepted";db.commit();v1=db.get(MesVehicle,v1.id);update_vehicle_state(db,v1.id,operational_state="SERVICE",expected_version=v1.version,actor="test");db.commit()
    assert db.get(MesVehicle,v1.id).operational_state=="SERVICE"
    v3=MesVehicle(vehicle_type="truck",registration_number="P3-SERVICE",max_payload_kg=1000,internal_length_mm=4000,internal_width_mm=2000,internal_height_mm=2000,is_active=True,operational_state="SERVICE",created_by="test",updated_by="test")
    v4=MesVehicle(vehicle_type="truck",registration_number="P3-INACTIVE",max_payload_kg=1000,internal_length_mm=4000,internal_width_mm=2000,internal_height_mm=2000,is_active=False,operational_state="INACTIVE",created_by="test",updated_by="test")
    t3=MesTrip(trip_number="P3-T3",vehicle_id=None,driver_user_id=None,project_id=project.id,release_id=release.id,destination_city="Toshkent",destination_site="Atlas",destination_address="Test",status="draft",created_by="test",updated_by="test")
    db.add_all([v3,v4,t3]);db.commit();expect("vehicle_not_available",lambda:update_trip_assignment(db,t3.id,vehicle_id=v3.id,driver_user_id=None,expected_version=t3.version,actor="test"));db.rollback();t3=db.get(MesTrip,t3.id);expect("vehicle_not_available",lambda:update_trip_assignment(db,t3.id,vehicle_id=v4.id,driver_user_id=None,expected_version=t3.version,actor="test"));db.rollback()
    t3=db.get(MesTrip,t3.id);update_trip_plan(db,t3.id,planned_loading_at=None,planned_departure_at=None,delivery_deadline_at=None,expected_version=t3.version,actor="test");db.commit();assert db.get(MesTrip,t3.id).delivery_deadline_at is None
    t3=db.get(MesTrip,t3.id);t3.status="delivered";db.commit();t3=db.get(MesTrip,t3.id);expect("trip_planning_locked",lambda:update_trip_plan(db,t3.id,planned_loading_at=None,planned_departure_at=None,delivery_deadline_at=None,expected_version=t3.version,actor="test"));db.rollback()
    db.close()
