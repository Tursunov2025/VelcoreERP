"""Hardened GPS tracking for canonical MesTrip shipments."""
import hashlib, json, secrets
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models import MesGpsDevice, MesTrip, MesTripLatestLocation, MesTripLocation, MesTripTrackingSession, User
from services.audit import log_action
from services.platform_administration import get_versioned_setting

GPS_POLICY_DEFAULTS={"moving_interval_seconds":15,"stationary_interval_seconds":120,"significant_displacement_meters":300,"offline_retention_hours":72,"maximum_batch_size":100,"stale_threshold_seconds":180,"route_deviation_meters":500,"long_stop_seconds":900,"history_retention_days":90}
GPS_POLICY_BOUNDS={"moving_interval_seconds":(5,300),"stationary_interval_seconds":(30,1800),"significant_displacement_meters":(10,5000),"offline_retention_hours":(72,2160),"maximum_batch_size":(1,250),"stale_threshold_seconds":(30,3600),"route_deviation_meters":(50,10000),"long_stop_seconds":(60,86400),"history_retention_days":(7,730)}
TRACKABLE_STATUSES={"loading","loaded","dispatched","in_transit"}; FINAL_STATUSES={"delivered","accepted","cancelled"}
HEALTH_STATES={"permission_missing","gps_disabled","approximate_only","background_permission_missing","battery_restricted","offline","syncing","active","stale","stopped","revoked"}

class TripTrackingError(ValueError):
    def __init__(self,code,message,status_code=409): super().__init__(message); self.code=code; self.status_code=status_code

def gps_policy(db):
    raw=get_versioned_setting(db,"platform.integration.gps",GPS_POLICY_DEFAULTS); out=dict(GPS_POLICY_DEFAULTS)
    for key,(low,high) in GPS_POLICY_BOUNDS.items():
        value=raw.get(key,out[key]); out[key]=int(value) if isinstance(value,(int,float)) and not isinstance(value,bool) and low<=value<=high else out[key]
    return out

def validate_policy(values):
    if set(values)!=set(GPS_POLICY_DEFAULTS): raise TripTrackingError("invalid_gps_policy","Invalid GPS policy keys",422)
    for key,(low,high) in GPS_POLICY_BOUNDS.items():
        value=values[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not low<=value<=high: raise TripTrackingError("invalid_gps_policy",f"Invalid {key}",422)
    return {key:int(values[key]) for key in GPS_POLICY_DEFAULTS}

def require_assigned_trip(db,trip_id,user,lock=False):
    q=db.query(MesTrip)
    if lock:q=q.with_for_update()
    trip=q.filter_by(id=trip_id).first()
    if not trip or trip.driver_user_id!=user.id: raise TripTrackingError("trip_not_found","Trip not found",404)
    return trip

def _hash_token(token): return hashlib.sha256(token.encode()).hexdigest()
def _hash_point(point):
    data={k:(v.isoformat() if isinstance(v,datetime) else v) for k,v in point.items()}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def serialize_session(row):
    keys=("id","trip_id","vehicle_id","driver_user_id","client_session_id","status","started_at","stopped_at","last_received_at","last_contact_at","authorization_expires_at","revoked_at","health_state","queued_point_count","latest_accuracy_m","latest_battery_level")
    payload = {k:getattr(row,k) for k in keys}
    payload["device_id"] = getattr(row, "device_id", None)
    device = getattr(row, "device", None)
    payload["device_identifier"] = device.device_identifier if device else None
    return payload

def serialize_location(row):
    if not row:return None
    keys=("id","session_id","trip_id","latitude","longitude","accuracy_m","speed_kmh","heading_deg","battery_level","captured_at","received_at")
    return {k:getattr(row,k) for k in keys if hasattr(row,k)}|{"was_queued":getattr(row,"was_queued",False)}

def start_session(db,trip_id,user,client_session_id,device_identifier=None):
    trip=require_assigned_trip(db,trip_id,user,True)
    if trip.status not in TRACKABLE_STATUSES: raise TripTrackingError("trip_not_trackable","Trip not trackable")
    device = None
    if device_identifier:
        identifier = str(device_identifier).strip().upper()
        device = db.query(MesGpsDevice).filter_by(device_identifier=identifier, status="active").first()
        if not device or device.vehicle_id != trip.vehicle_id or (device.driver_user_id is not None and device.driver_user_id != user.id):
            raise TripTrackingError("tracking_device_scope_mismatch", "GPS device is not bound to this trip vehicle or driver", 409)
    existing=db.query(MesTripTrackingSession).filter_by(client_session_id=client_session_id).first()
    if existing and (existing.trip_id!=trip.id or existing.driver_user_id!=user.id or existing.vehicle_id!=trip.vehicle_id): raise TripTrackingError("idempotency_conflict","Session scope conflict")
    row=existing or db.query(MesTripTrackingSession).filter_by(trip_id=trip.id,driver_user_id=user.id,status="active").first()
    if row and row.status!="active": raise TripTrackingError("tracking_session_stopped","Session stopped")
    created=row is None
    if created: row=MesTripTrackingSession(trip_id=trip.id,vehicle_id=trip.vehicle_id,driver_user_id=user.id,device_id=device.id if device else None,client_session_id=client_session_id,status="active"); db.add(row)
    elif device is not None and row.device_id not in (None, device.id):
        raise TripTrackingError("tracking_device_scope_mismatch", "Session is bound to a different GPS device", 409)
    elif device is not None and row.device_id is None:
        row.device_id = device.id
    token=secrets.token_urlsafe(32); now=datetime.utcnow(); row.authorization_hash=_hash_token(token); row.authorization_expires_at=now+timedelta(minutes=30); row.last_contact_at=now; row.health_state="active"
    try:db.flush()
    except IntegrityError as exc: raise TripTrackingError("idempotency_conflict","Session conflict") from exc
    if created:log_action(db,user.username,"gps_tracking_start","mes_trip",trip.id,f"session={row.id}")
    return row,token

def authorize_session(db,session_id,user,token,active_required=True):
    row=db.query(MesTripTrackingSession).with_for_update().filter_by(id=session_id).first()
    if not row or row.driver_user_id!=user.id: raise TripTrackingError("tracking_authorization_invalid","Invalid tracking authorization",401)
    if row.status=="revoked":raise TripTrackingError("tracking_authorization_revoked","Authorization revoked",403)
    if not token or not secrets.compare_digest(row.authorization_hash or "",_hash_token(token)): raise TripTrackingError("tracking_authorization_invalid","Invalid tracking authorization",401)
    if active_required and row.status!="active":raise TripTrackingError("tracking_session_stopped","Session stopped")
    if not row.authorization_expires_at or row.authorization_expires_at<=datetime.utcnow():raise TripTrackingError("tracking_authorization_expired","Authorization expired",401)
    trip=require_assigned_trip(db,row.trip_id,user)
    if trip.vehicle_id!=row.vehicle_id or trip.status in FINAL_STATUSES:raise TripTrackingError("tracking_scope_mismatch","Tracking scope mismatch")
    return row

def append_locations(db,session_id,user,token,points):
    session=authorize_session(db,session_id,user,token)
    return append_locations_for_session(db, session, points)

def append_locations_for_session(db, session, points):
    """Persist canonical GPS points for an already-authorized tracking session.

    Protocol adapters must resolve and lock the canonical device/session before
    calling this function.  The public HTTP path continues to authenticate via
    ``authorize_session`` above; this function is the single persistence/latest
    projection/lifecycle writer shared by both transports.
    """
    user = db.get(User, session.driver_user_id)
    if not user:
        raise TripTrackingError("tracking_scope_mismatch", "Tracking driver is unavailable")
    policy=gps_policy(db); now=datetime.utcnow()
    if len(points)>policy["maximum_batch_size"]:raise TripTrackingError("tracking_batch_too_large","Batch too large",413)
    oldest=now-timedelta(hours=policy["offline_retention_hours"]); newest=now+timedelta(minutes=5)
    for p in points:
        captured=p["captured_at"].replace(tzinfo=None)
        if captured<oldest or captured>newest:raise TripTrackingError("tracking_time_out_of_range","Captured time out of range",422)
    ids=[p["client_point_id"] for p in points]; existing={r.client_point_id:r for r in db.query(MesTripLocation).filter(MesTripLocation.session_id==session.id,MesTripLocation.client_point_id.in_(ids)).all()} if ids else {}
    accepted=duplicates=0; inserted=[]
    for p in points:
        h=_hash_point(p); prior=existing.get(p["client_point_id"])
        if prior:
            if prior.payload_hash!=h:raise TripTrackingError("tracking_client_point_conflict","Client point conflict")
            duplicates+=1;continue
        stored_point = dict(p)
        # SQLite returns persisted DateTime values without timezone metadata. Keep
        # the idempotency hash tied to the exact client payload, but normalize the
        # authoritative stored timestamp so consecutive points are comparable.
        stored_point["captured_at"] = p["captured_at"].replace(tzinfo=None)
        row=MesTripLocation(session_id=session.id,trip_id=session.trip_id,vehicle_id=session.vehicle_id,driver_user_id=user.id,payload_hash=h,**stored_point);db.add(row);db.flush();existing[row.client_point_id]=row;inserted.append(row);accepted+=1
    for row in sorted(inserted,key=lambda x:(x.captured_at,x.id)):
        dialect=db.get_bind().dialect.name
        latest=(db.query(MesTripLatestLocation).with_for_update().filter_by(trip_id=session.trip_id).first()
                if dialect=="postgresql" else db.get(MesTripLatestLocation,session.trip_id))
        if latest is None:
            latest=MesTripLatestLocation(trip_id=session.trip_id,session_id=session.id,vehicle_id=session.vehicle_id,driver_user_id=user.id,location_id=row.id,latitude=row.latitude,longitude=row.longitude,accuracy_m=row.accuracy_m,speed_kmh=row.speed_kmh,heading_deg=row.heading_deg,battery_level=row.battery_level,captured_at=row.captured_at,received_at=row.received_at);db.add(latest);db.flush()
        # SQLite uses a conditional timestamp/id comparison; PostgreSQL holds a row lock above.
        elif (row.captured_at,row.id)>(latest.captured_at,latest.location_id):
            latest.session_id=row.session_id;latest.location_id=row.id
            for key in ("latitude","longitude","accuracy_m","speed_kmh","heading_deg","battery_level","captured_at","received_at"):setattr(latest,key,getattr(row,key))
    session.last_received_at=now;session.last_contact_at=now;session.health_state="active";session.queued_point_count=max(0,(session.queued_point_count or 0)-accepted)
    if inserted:
        newest_row=max(inserted,key=lambda x:(x.captured_at,x.id));session.latest_accuracy_m=newest_row.accuracy_m;session.latest_battery_level=newest_row.battery_level
        from services.trip_lifecycle import evaluate_gps_in_transit
        evaluate_gps_in_transit(db,newest_row)
    db.flush();return {"accepted":accepted,"duplicates":duplicates,"received_at":now,"latest":serialize_location(db.get(MesTripLatestLocation,session.trip_id))}

def heartbeat(db,session_id,user,token,state,queued,accuracy,battery):
    row=authorize_session(db,session_id,user,token)
    if state not in HEALTH_STATES-{"stopped","revoked","stale"}:raise TripTrackingError("invalid_tracking_health","Invalid health",422)
    row.last_contact_at=datetime.utcnow();row.health_state=state;row.queued_point_count=queued;row.latest_accuracy_m=accuracy;row.latest_battery_level=battery;return row

def stop_session(db,session_id,user,token):
    row=authorize_session(db,session_id,user,token,False)
    if row.status!="stopped":row.status="stopped";row.health_state="stopped";row.stopped_at=datetime.utcnow();log_action(db,user.username,"gps_tracking_stop","mes_trip",row.trip_id,f"session={row.id}")
    return row

def revoke_session(db,session_id,actor):
    row=db.query(MesTripTrackingSession).with_for_update().filter_by(id=session_id).first()
    if not row:raise TripTrackingError("tracking_session_not_found","Session not found",404)
    if row.status!="revoked":row.status="revoked";row.health_state="revoked";row.revoked_at=datetime.utcnow();row.revoked_by=actor.username;row.authorization_hash=None;log_action(db,actor.username,"gps_tracking_revoke","mes_trip",row.trip_id,f"session={row.id}")
    return row

def effective_health(row,policy,now=None):
    if row.status in {"stopped","revoked"}:return row.status
    return "stale" if not row.last_contact_at or ((now or datetime.utcnow())-row.last_contact_at).total_seconds()>policy["stale_threshold_seconds"] else row.health_state

def cleanup_history(db,now=None):
    cutoff=(now or datetime.utcnow())-timedelta(days=gps_policy(db)["history_retention_days"]); protected=db.query(MesTripLatestLocation.location_id)
    rows=db.query(MesTripLocation).filter(MesTripLocation.captured_at<cutoff,~MesTripLocation.id.in_(protected)).all()
    for row in rows:db.delete(row)
    return len(rows)
