"""Canonical manual route planning for MesTrip."""
from __future__ import annotations
from datetime import datetime
from math import asin, cos, radians, sin, sqrt

from models import MesTrip, MesTripRoute, MesTripRouteStop
from services.audit import log_action

STATUSES = {"draft", "active", "completed", "cancelled"}

class TripRouteError(ValueError):
    def __init__(self, code, message, status_code=422):
        super().__init__(message); self.code=code; self.status_code=status_code

def _coordinate(lat, lon):
    lat=float(lat); lon=float(lon)
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise TripRouteError("invalid_route_coordinates", "Route coordinates are outside geographic range")
    return lat,lon

def _distance(a,b):
    lat1,lon1=map(radians,a); lat2,lon2=map(radians,b)
    dlat=lat2-lat1; dlon=lon2-lon1
    h=sin(dlat/2)**2+cos(lat1)*cos(lat2)*sin(dlon/2)**2
    return 6371000*2*asin(sqrt(h))

def _rebuild(route):
    stops=sorted(route.stops,key=lambda x:(x.sequence,x.id or 0))
    points=[[route.origin_lat,route.origin_lon],*[[x.latitude,x.longitude] for x in stops],[route.destination_lat,route.destination_lon]]
    route.geometry_json=points
    route.planned_distance_m=round(sum(_distance(points[i],points[i+1]) for i in range(len(points)-1)),1)
    route.planned_duration_s=round(route.planned_distance_m/13.89) if route.planned_distance_m else 0

def serialize_route(route):
    if not route:return None
    return {"id":route.id,"trip_id":route.trip_id,"status":route.status,"origin":{"name":route.origin_name,"latitude":route.origin_lat,"longitude":route.origin_lon},"destination":{"name":route.destination_name,"latitude":route.destination_lat,"longitude":route.destination_lon},"planned_distance_m":route.planned_distance_m,"planned_duration_s":route.planned_duration_s,"provider":route.provider,"geometry":route.geometry_json or [],"version":route.version,"created_by":route.created_by,"updated_by":route.updated_by,"created_at":route.created_at,"updated_at":route.updated_at,"stops":[{"id":s.id,"sequence":s.sequence,"stop_type":s.stop_type,"name":s.name,"address":s.address,"latitude":s.latitude,"longitude":s.longitude,"planned_arrival_at":s.planned_arrival_at,"notes":s.notes} for s in sorted(route.stops,key=lambda x:x.sequence)]}

def get_route(db,trip_id):
    if not db.get(MesTrip,trip_id):raise TripRouteError("trip_not_found","Trip not found",404)
    return db.query(MesTripRoute).filter(MesTripRoute.trip_id==trip_id,MesTripRoute.status!="cancelled").order_by(MesTripRoute.id.desc()).first() or db.query(MesTripRoute).filter_by(trip_id=trip_id).order_by(MesTripRoute.id.desc()).first()

def create_route(db,trip_id,data,actor):
    if not db.get(MesTrip,trip_id):raise TripRouteError("trip_not_found","Trip not found",404)
    if db.query(MesTripRoute).filter_by(trip_id=trip_id,status="active").first():raise TripRouteError("active_route_exists","An active route already exists",409)
    olat,olon=_coordinate(data.origin_lat,data.origin_lon); dlat,dlon=_coordinate(data.destination_lat,data.destination_lon)
    row=MesTripRoute(trip_id=trip_id,status="draft",origin_name=data.origin_name.strip(),origin_lat=olat,origin_lon=olon,destination_name=data.destination_name.strip(),destination_lat=dlat,destination_lon=dlon,provider="manual_straight_line",created_by=actor,updated_by=actor)
    db.add(row);db.flush();_rebuild(row);log_action(db,actor,"create","trip_route",row.id,f"trip={trip_id}");return row

def update_route(db,route,data,actor):
    if route.version!=data.expected_version:raise TripRouteError("route_version_conflict","Route was changed by another user",409)
    if route.status=="cancelled":raise TripRouteError("route_cancelled","Cancelled route cannot be edited",409)
    before=serialize_route(route)
    for prefix in ("origin","destination"):
        name=getattr(data,f"{prefix}_name",None); lat=getattr(data,f"{prefix}_lat",None); lon=getattr(data,f"{prefix}_lon",None)
        if name is not None:setattr(route,f"{prefix}_name",name.strip())
        if lat is not None or lon is not None:
            a,b=_coordinate(lat if lat is not None else getattr(route,f"{prefix}_lat"),lon if lon is not None else getattr(route,f"{prefix}_lon"));setattr(route,f"{prefix}_lat",a);setattr(route,f"{prefix}_lon",b)
    route.updated_by=actor;route.updated_at=datetime.utcnow();route.version+=1;_rebuild(route);log_action(db,actor,"update","trip_route",route.id,f"version={before['version']}->{route.version}");return route

def set_status(db,route,status,expected_version,actor):
    status=status.strip().lower()
    if status not in STATUSES:raise TripRouteError("invalid_route_status","Route status is invalid")
    if route.version!=expected_version:raise TripRouteError("route_version_conflict","Route was changed by another user",409)
    if route.status=="cancelled" and status!="cancelled":raise TripRouteError("route_cancelled","Cancelled route cannot be changed",409)
    if status=="active" and db.query(MesTripRoute).filter(MesTripRoute.trip_id==route.trip_id,MesTripRoute.status=="active",MesTripRoute.id!=route.id).first():raise TripRouteError("active_route_exists","An active route already exists",409)
    route.status=status;route.version+=1;route.updated_by=actor;route.updated_at=datetime.utcnow();log_action(db,actor,status,"trip_route",route.id,f"trip={route.trip_id}");return route

def add_stop(db,route,data,actor):
    if route.status=="cancelled":raise TripRouteError("route_cancelled","Cancelled route cannot be edited",409)
    lat,lon=_coordinate(data.latitude,data.longitude)
    if db.query(MesTripRouteStop).filter_by(route_id=route.id,sequence=data.sequence).first():raise TripRouteError("duplicate_stop_sequence","Stop sequence already exists",409)
    row=MesTripRouteStop(route_id=route.id,sequence=data.sequence,stop_type=data.stop_type,name=data.name.strip(),address=data.address or "",latitude=lat,longitude=lon,planned_arrival_at=data.planned_arrival_at,notes=data.notes or "")
    db.add(row);db.flush();route.version+=1;_rebuild(route);log_action(db,actor,"add_stop","trip_route",route.id,f"stop={row.id}");return row

def update_stop(db,route,stop,data,actor):
    if route.version!=data.expected_version:raise TripRouteError("route_version_conflict","Route was changed by another user",409)
    if route.status=="cancelled":raise TripRouteError("route_cancelled","Cancelled route cannot be edited",409)
    if data.sequence!=stop.sequence and db.query(MesTripRouteStop).filter(MesTripRouteStop.route_id==route.id,MesTripRouteStop.sequence==data.sequence,MesTripRouteStop.id!=stop.id).first():raise TripRouteError("duplicate_stop_sequence","Stop sequence already exists",409)
    lat,lon=_coordinate(data.latitude,data.longitude)
    for k in ("sequence","stop_type","name","address","planned_arrival_at","notes"):setattr(stop,k,getattr(data,k))
    stop.latitude=lat;stop.longitude=lon;route.version+=1;_rebuild(route);log_action(db,actor,"update_stop","trip_route",route.id,f"stop={stop.id}");return stop

def delete_stop(db,route,stop,expected_version,actor):
    if route.version!=expected_version:raise TripRouteError("route_version_conflict","Route was changed by another user",409)
    db.delete(stop);db.flush();route.version+=1;_rebuild(route);log_action(db,actor,"delete_stop","trip_route",route.id,f"stop={stop.id}")

def reorder_stops(db,route,stop_ids,expected_version,actor):
    if route.version!=expected_version:raise TripRouteError("route_version_conflict","Route was changed by another user",409)
    rows=sorted(route.stops,key=lambda x:x.id); by_id={x.id:x for x in rows}
    if len(stop_ids)!=len(rows) or set(stop_ids)!=set(by_id):raise TripRouteError("invalid_stop_order","Stop order must contain every stop exactly once")
    # Move through a positive temporary range so both the positivity check and
    # the unique (route, sequence) constraint remain valid on every database.
    for i,sid in enumerate(stop_ids,1):by_id[sid].sequence=1_000_000+i
    db.flush()
    for i,sid in enumerate(stop_ids,1):by_id[sid].sequence=i
    route.version+=1;_rebuild(route);log_action(db,actor,"reorder_stops","trip_route",route.id,f"count={len(rows)}")
