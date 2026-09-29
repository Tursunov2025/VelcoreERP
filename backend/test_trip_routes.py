from __future__ import annotations
import os,tempfile
from pathlib import Path

TMP=Path(tempfile.mkdtemp(prefix="azmus_trip_route_")); DB=TMP/"route.db"
os.environ.update({"DATABASE_URL":f"sqlite:///{DB.as_posix()}","DB_PATH":str(DB),"DATA_ROOT":str(TMP),"DATABASE_GUARD":"false","SKIP_DEMO_SEED":"true","JWT_SECRET_KEY":"route-test-secret"})

from fastapi.testclient import TestClient
from auth.security import hash_password
from database import Base,SessionLocal,engine
from main import app
from models import AuditLog,MesTrip,MesVehicle,ProductionProject,ProjectReleaseSnapshot,User,UserPermission

def setup_module():
    Base.metadata.create_all(engine)
    db=SessionLocal()
    admin=User(username="route-admin",password_hash=hash_password("Route!2026"),role="admin",department="Logistika",is_active=True)
    driver=User(username="route-driver",password_hash=hash_password("Route!2026"),role="driver",department="Logistika",is_active=True)
    other=User(username="route-other",password_hash=hash_password("Route!2026"),role="driver",department="Logistika",is_active=True)
    db.add_all([admin,driver,other]);db.flush()
    db.add_all([UserPermission(user_id=driver.id,module="gps_trip_view",enabled=True),UserPermission(user_id=other.id,module="gps_trip_view",enabled=True)])
    p=ProductionProject(project_code="ROUTE-P",project_name="Route",customer_name_snapshot="Test",destination_city="Toshkent",site_name="Atlas",full_address="Atlas",status="released",release_revision=1,created_by="route-admin")
    db.add(p);db.flush(); rel=ProjectReleaseSnapshot(project_id=p.id,revision=1,source_project_version=1,idempotency_key="route-release",checksum="0"*64,released_by="route-admin");db.add(rel);db.flush()
    v=MesVehicle(vehicle_type="truck",registration_number="01 ROUTE",max_payload_kg=1000,internal_length_mm=1,internal_width_mm=1,internal_height_mm=1,created_by="route-admin",updated_by="route-admin");db.add(v);db.flush()
    db.add(MesTrip(trip_number="ROUTE-1",vehicle_id=v.id,driver_user_id=driver.id,project_id=p.id,release_id=rel.id,destination_city="Toshkent",destination_site="Atlas",destination_address="Atlas",status="dispatched",created_by="route-admin",updated_by="route-admin"));db.commit();db.close()

def auth(client,name):
    r=client.post('/auth/login',json={'username':name,'password':'Route!2026'});assert r.status_code==200,r.text;return {'Authorization':f"Bearer {r.json()['access_token']}"}

def test_route_full_contract_permissions_version_and_audit():
    c=TestClient(app); admin=auth(c,'route-admin'); driver=auth(c,'route-driver'); other=auth(c,'route-other')
    body={'origin_name':'Factory','origin_lat':40.38,'origin_lon':71.78,'destination_name':'Atlas','destination_lat':41.30,'destination_lon':69.24}
    r=c.post('/mes/finished-logistics/trips/1/route',headers=admin,json=body);assert r.status_code==201,r.text; route=r.json();assert route['provider']=='manual_straight_line' and len(route['geometry'])==2
    assert c.post('/mes/finished-logistics/trips/1/route',headers=driver,json=body).status_code==403
    for i in range(1,4):
        payload={'expected_version':route['version'],'sequence':i,'stop_type':'waypoint','name':f'Stop {i}','address':'','latitude':40.4+i*.1,'longitude':71.7-i*.2,'planned_arrival_at':None,'notes':''}
        r=c.post('/mes/finished-logistics/trips/1/route/stops',headers=admin,json=payload);assert r.status_code==201,r.text;route=r.json()
    assert [s['sequence'] for s in route['stops']]==[1,2,3] and len(route['geometry'])==5
    ids=[s['id'] for s in route['stops']]
    r=c.post('/mes/finished-logistics/trips/1/route/stops/reorder',headers=admin,json={'expected_version':route['version'],'stop_ids':list(reversed(ids))});assert r.status_code==200,r.text;route=r.json();assert [s['id'] for s in route['stops']]==list(reversed(ids))
    stop=route['stops'][0]; r=c.put(f"/mes/finished-logistics/trips/1/route/stops/{stop['id']}",headers=admin,json={**stop,'expected_version':route['version'],'name':'Updated'});assert r.status_code==200,r.text;route=r.json();assert route['stops'][0]['name']=='Updated'
    stale=c.put('/mes/finished-logistics/trips/1/route',headers=admin,json={**body,'expected_version':1});assert stale.status_code==409
    invalid=c.put('/mes/finished-logistics/trips/1/route',headers=admin,json={**body,'origin_lat':100,'expected_version':route['version']});assert invalid.status_code==422
    r=c.post('/mes/finished-logistics/trips/1/route/status',headers=admin,json={'expected_version':route['version'],'status':'active'});assert r.status_code==200;route=r.json()
    assert c.post('/mes/finished-logistics/trips/1/route',headers=admin,json=body).status_code==409
    assert c.get('/mes/finished-logistics/trips/1/route',headers=driver).status_code==200
    assert c.get('/mes/finished-logistics/trips/1/route',headers=other).status_code==403
    assert c.delete(f"/mes/finished-logistics/trips/1/route?expected_version={route['version']}",headers=admin).status_code==200
    db=SessionLocal();assert db.query(AuditLog).filter(AuditLog.entity_type=='trip_route').count()>=7;db.close()
