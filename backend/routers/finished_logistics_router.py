"""Finished warehouse locations, vehicles, trips, and safe delivery evidence APIs."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from database import get_db
from models import (
    MesFinishedGoodsPlacement, MesJobPackage, MesShipmentItem, MesTrip, MesTripEvidence,
    MesGpsDevice, MesTripDocumentSnapshot, MesTripRoute, MesTripRouteStop, MesVehicle, MesWarehouseLocation, User, UserIdentityProfile,
)
from services.audit import log_action
from services.finished_logistics import (
    LogisticsError, attach_dispatch, create_location_node, create_trip, create_vehicle,
    evidence_path, placement_totals, save_trip_evidence, transition_trip, update_vehicle,
)
from services.mes_warehouse_terminal import serialize_location
from services.permissions import user_has_permission
from services.logistics_planning import (
    LogisticsPlanningError, CONFLICTING_TRIP_STATUSES, derive_trip_alerts, sla_state,
    update_trip_assignment, update_trip_plan, update_vehicle_state,
)
from services.shipment_execution import (
    ShipmentError, accept_delivery, assign_placement, automatic_initial_plan,
    confirm_loading, create_consolidated_trip, final_dispatch, record_delivery, remove_assignment, save_plan,
    serialize_plan, trip_progress, validate_plan,
)
from services.load_corrections import (
    correction_history, reload_package, replace_package, return_to_warehouse,
    transfer_package, unload_package,
)
from services.trip_lifecycle import TripLifecycleError, automatic_arrival_readiness, confirm_arrival
from services.logistics_master_data import (
    create_driver, create_gps_device, serialize_device, serialize_driver,
    set_driver_status, unbind_gps_device, update_driver, update_gps_device,
)
from services.trip_documents import DOCUMENT_TYPES, document_path, generate_trip_document
from services.trip_routes import (TripRouteError, add_stop, create_route, delete_stop,
    get_route, reorder_stops, serialize_route, set_status, update_route, update_stop)


router = APIRouter(prefix="/mes/finished-logistics", tags=["mes-finished-logistics"])


class LocationNodeCreate(BaseModel):
    parent_id: int | None = None
    location_type: str
    segment_code: str = Field(..., min_length=1, max_length=64)
    description: str = ""


class VehicleCreate(BaseModel):
    vehicle_type: str = Field(..., min_length=1, max_length=64)
    registration_number: str = Field(..., min_length=1, max_length=32)
    internal_code: str = Field(default="", max_length=64)
    model: str = Field(default="", max_length=120)
    driver_name: str = ""
    driver_phone: str = ""
    max_payload_kg: float | None = Field(default=None, gt=0)
    load_capacity: float | None = Field(default=None, gt=0)
    internal_length_mm: float
    internal_width_mm: float
    internal_height_mm: float
    max_volume_m3: float | None = None
    is_active: bool = True
    notes: str = ""


class VehicleUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    registration_number: str | None = Field(default=None, min_length=1, max_length=32)
    vehicle_type: str | None = None
    internal_code: str | None = None
    model: str | None = None
    driver_name: str | None = None
    driver_phone: str | None = None
    max_payload_kg: float | None = None
    load_capacity: float | None = Field(default=None, gt=0)
    internal_length_mm: float | None = None
    internal_width_mm: float | None = None
    internal_height_mm: float | None = None
    max_volume_m3: float | None = None
    is_active: bool | None = None
    notes: str | None = None


class VehicleStateUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    operational_state: str


class DriverCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    department: str = ""
    full_name: str = ""
    employee_id: str = ""
    position: str = ""
    phone: str = ""
    email: str = ""
    telegram: str = ""
    avatar_url: str = ""
    is_active: bool = True


class DriverUpdate(BaseModel):
    username: str = Field(..., min_length=2, max_length=100)
    password: str | None = Field(default=None, max_length=128)
    department: str = ""
    full_name: str | None = None
    employee_id: str | None = None
    position: str | None = None
    phone: str | None = None
    email: str | None = None
    telegram: str | None = None
    avatar_url: str | None = None
    is_active: bool | None = None


class DriverStatusUpdate(BaseModel):
    active: bool


class TripDocumentCreate(BaseModel):
    document_type: str
    language: str = "uz"


class GpsDeviceCreate(BaseModel):
    device_identifier: str = Field(..., min_length=1, max_length=180)
    vehicle_id: int = Field(..., ge=1)
    driver_user_id: int | None = Field(default=None, ge=1)
    status: str = "active"
    protocol: str = "custom_http"
    notes: str = ""


class GpsDeviceUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    device_identifier: str | None = Field(default=None, min_length=1, max_length=180)
    vehicle_id: int | None = Field(default=None, ge=1)
    driver_user_id: int | None = Field(default=None, ge=1)
    status: str | None = None
    protocol: str | None = None
    notes: str | None = None


class GpsDeviceUnbind(BaseModel):
    expected_version: int = Field(..., ge=1)

class TripRouteCreate(BaseModel):
    origin_name: str = Field(..., min_length=1, max_length=255)
    origin_lat: float
    origin_lon: float
    destination_name: str = Field(..., min_length=1, max_length=255)
    destination_lat: float
    destination_lon: float

class TripRouteUpdate(TripRouteCreate):
    expected_version: int = Field(..., ge=1)

class TripRouteStatus(BaseModel):
    expected_version: int = Field(..., ge=1)
    status: str

class TripRouteStopInput(BaseModel):
    expected_version: int = Field(..., ge=1)
    sequence: int = Field(..., ge=1)
    stop_type: str = Field(default="waypoint", max_length=32)
    name: str = Field(..., min_length=1, max_length=255)
    address: str = Field(default="", max_length=500)
    latitude: float
    longitude: float
    planned_arrival_at: datetime | None = None
    notes: str = Field(default="", max_length=1000)

class TripRouteReorder(BaseModel):
    expected_version: int = Field(..., ge=1)
    stop_ids: list[int]


class TripCreate(BaseModel):
    trip_number: str = Field(..., min_length=1, max_length=80)
    vehicle_id: int
    driver_user_id: int | None = None
    project_id: int
    release_id: int
    destination_city: str
    destination_site: str
    destination_address: str
    planned_departure_at: datetime | None = None
    planned_loading_at: datetime | None = None
    delivery_deadline_at: datetime | None = None
    notes: str = ""
    evidence_policy: str = "required"
    completeness_required: bool = True


class ConsolidatedTripCreate(BaseModel):
    trip_number: str = Field(..., min_length=1, max_length=80)
    vehicle_id: int = Field(..., ge=1)
    driver_user_id: int = Field(..., ge=1)
    placement_ids: list[int] = Field(..., min_length=1, max_length=250)
    planned_departure_at: datetime | None = None
    planned_loading_at: datetime | None = None
    delivery_deadline_at: datetime | None = None
    notes: str = ""
    evidence_policy: str = "required"
    completeness_required: bool = False
    idempotency_key: str = Field(..., min_length=8, max_length=120)


class TripTransition(BaseModel):
    status: str
    expected_version: int = Field(..., ge=1)


class TripAssignmentUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    vehicle_id: int | None = None
    driver_user_id: int | None = None


class TripPlanningUpdate(BaseModel):
    expected_version: int = Field(..., ge=1)
    planned_loading_at: datetime | None = None
    planned_departure_at: datetime | None = None
    delivery_deadline_at: datetime | None = None


class ShipmentAssign(BaseModel):
    placement_id: int
    dispatch_id: int | None = None
    planned_quantity: float | None = Field(None, gt=0)
    idempotency_key: str = Field(..., min_length=8, max_length=180)


class PlanPlacementInput(BaseModel):
    shipment_item_id: int
    x_mm: float = Field(..., ge=0)
    y_mm: float = Field(..., ge=0)
    rotation: int
    loading_sequence: int = Field(..., ge=1)
    expected_version: int | None = Field(None, ge=1)


class PlanUpdate(BaseModel):
    placements: list[PlanPlacementInput]


class LoadingConfirm(BaseModel):
    acknowledge_unknown_weight: bool = False
    idempotency_key: str = Field(..., min_length=8, max_length=180)


class CommandRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=180)


class DeliveryDisposition(BaseModel):
    item_id: int
    delivered_quantity: float = Field(..., ge=0)
    accepted_quantity: float = Field(..., ge=0)
    damaged_quantity: float = Field(..., ge=0)
    missing_quantity: float = Field(..., ge=0)
    notes: str = ""


class DeliveryRequest(BaseModel):
    dispositions: list[DeliveryDisposition]
    idempotency_key: str = Field(..., min_length=8, max_length=180)


class AcceptanceRequest(BaseModel):
    project_id: int | None = Field(default=None, ge=1)
    recipient_name: str = Field(..., min_length=1, max_length=160)
    notes: str = ""
    resolved_shortage_item_ids: list[int] = Field(default_factory=list)
    idempotency_key: str = Field(..., min_length=8, max_length=180)


class ArrivalRequest(BaseModel):
    expected_version: int = Field(..., ge=1)
    idempotency_key: str = Field(..., min_length=8, max_length=180)


class LoadCorrectionRequest(BaseModel):
    expected_trip_version: int = Field(..., ge=1)
    expected_item_version: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1, max_length=40)
    notes: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(..., min_length=8, max_length=180)


class LoadTransferRequest(LoadCorrectionRequest):
    target_trip_id: int = Field(..., ge=1)
    expected_target_trip_version: int = Field(..., ge=1)


class LoadReplaceRequest(LoadCorrectionRequest):
    replacement_placement_id: int = Field(..., ge=1)
    expected_replacement_version: int = Field(..., ge=1)


def _allowed(db: Session, user: User, terminal: str, project: str) -> bool:
    return user.role in ("admin", "super_admin") or (
        user_has_permission(db, user, terminal) and user_has_permission(db, user, project)
    )


def _warehouse(db: Session, user: User) -> None:
    if not _allowed(db, user, "mes_terminal_warehouse", "production_projects_package"):
        raise HTTPException(403, detail={"code": "permission_denied"})


def _dispatch(db: Session, user: User) -> None:
    if not _allowed(db, user, "mes_terminal_dispatch", "production_projects_dispatch"):
        raise HTTPException(403, detail={"code": "permission_denied"})


def _manage(db: Session, user: User, permission: str) -> None:
    if user.role in ("admin", "super_admin"):
        return
    if not user_has_permission(db, user, permission):
        raise HTTPException(403, detail={"code": "permission_denied"})


def _trip_operator(db: Session, user: User, trip_id: int) -> MesTrip:
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip:
        raise HTTPException(404, detail={"code": "trip_not_found"})
    if user.role == "driver" and trip.driver_user_id == user.id:
        return trip
    _dispatch(db, user)
    return trip


def _loading_correction_permission(db: Session, user: User, trip: MesTrip, *, transfer: bool = False) -> None:
    # Drivers never mutate cargo assignments. Existing dispatch operators may
    # correct while loading; a completed load requires the narrow supervisor
    # permission. Transfers always require their dedicated permission.
    if user.role in ("admin", "super_admin"):
        return
    if user.role == "driver":
        raise HTTPException(403, detail={"code": "permission_denied"})
    if transfer and not user_has_permission(db, user, "logistics_trip_transfer"):
        raise HTTPException(403, detail={"code": "permission_denied"})
    if trip.status == "loaded":
        if not user_has_permission(db, user, "logistics_loading_correct"):
            raise HTTPException(403, detail={"code": "permission_denied"})
        return
    _dispatch(db, user)


def _error(exc: LogisticsError):
    raise HTTPException(exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


def _shipment_error(exc: ShipmentError):
    raise HTTPException(exc.status_code, detail={"code": exc.code, "message": str(exc), **exc.context}) from exc


def _vehicle(row: MesVehicle) -> dict:
    return {key: getattr(row, key) for key in (
        "id", "vehicle_type", "registration_number", "internal_code", "model", "driver_name", "driver_phone",
        "max_payload_kg", "internal_length_mm", "internal_width_mm", "internal_height_mm",
        "max_volume_m3", "is_active", "operational_state", "version", "notes", "created_at", "updated_at",
    )} | {"load_capacity": row.max_payload_kg}


def _trip(row: MesTrip) -> dict:
    payload = {key: getattr(row, key) for key in (
        "id", "trip_number", "vehicle_id", "driver_user_id", "project_id", "release_id",
        "driver_name_snapshot", "driver_phone_snapshot", "destination_city",
        "destination_site", "destination_address", "planned_loading_at", "planned_departure_at", "delivery_deadline_at",
        "actual_departure_at", "arrived_at", "status", "notes", "version",
        "evidence_policy", "completeness_required",
        "created_by", "updated_by", "created_at", "updated_at",
    )}
    payload["sla_state"] = sla_state(row)
    active_items = [item for item in row.shipment_items if item.assignment_status == "active"]
    projects = {}
    for item in active_items:
        project = item.project_line.project if item.project_line else None
        projects[item.project_id] = {
            "id": item.project_id,
            "code": project.project_code if project else f"#{item.project_id}",
            "name": project.project_name if project else "",
            "destination_city": project.destination_city if project else "",
            "destination_site": project.site_name if project else "",
        }
    payload["primary_project_id"] = row.project_id
    payload["projects"] = list(projects.values())
    payload["project_count"] = len(projects) or 1
    payload["package_count"] = len(active_items)
    return payload


def _planning_error(exc: LogisticsPlanningError):
    raise HTTPException(exc.status_code, detail={"code": exc.code, "message": str(exc), **exc.context}) from exc

def _route_error(exc: TripRouteError):
    raise HTTPException(exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


def _evidence(row: MesTripEvidence) -> dict:
    return {key: getattr(row, key) for key in (
        "id", "trip_id", "project_id", "evidence_type", "actor", "occurred_at",
        "latitude", "longitude", "note", "original_filename", "mime_type",
        "file_size", "checksum", "created_at",
    )}


@router.post("/locations", status_code=201)
def location_create(data: LocationNodeCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _warehouse(db, user)
    try:
        row = create_location_node(db, parent_id=data.parent_id, location_type=data.location_type,
                                   segment_code=data.segment_code, description=data.description, actor=user.username)
        db.commit()
        return serialize_location(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.get("/locations")
def location_list(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _warehouse(db, user)
    query = db.query(MesWarehouseLocation)
    if not include_inactive:
        query = query.filter(MesWarehouseLocation.is_active.is_(True))
    return {"locations": [serialize_location(row) for row in query.order_by(MesWarehouseLocation.code).all()]}


@router.get("/warehouse-totals")
def warehouse_totals(project_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _warehouse(db, user)
    return placement_totals(db, project_id)


@router.get("/placements")
def placement_list(project_id: int | None = None, release_id: int | None = None,
                   status: str = "placed", db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """Eligible finished-placement snapshots for the existing shipment workflow."""
    _dispatch(db, user)
    query = db.query(MesFinishedGoodsPlacement)
    if project_id is not None:
        query = query.filter(MesFinishedGoodsPlacement.project_id == project_id)
    if release_id is not None:
        query = query.filter(MesFinishedGoodsPlacement.release_id == release_id)
    if status:
        query = query.filter(MesFinishedGoodsPlacement.status == status.strip().lower())
    rows = query.order_by(MesFinishedGoodsPlacement.placed_at, MesFinishedGoodsPlacement.id).all()
    items = []
    for row in rows:
        package = db.get(MesJobPackage, row.package_id) if row.package_id else None
        items.append({
            "id": row.id, "project_id": row.project_id, "project_line_id": row.project_line_id,
            "template_id": row.template_id, "release_id": row.release_id,
            "package_id": row.package_id, "package_number": package.package_number if package else None,
            "passport_serials": [p.serial_number for p in sorted(getattr(package, "product_passports", []), key=lambda item: item.unit_index)] if package else [],
            "passport_count": len(getattr(package, "product_passports", [])) if package else 0,
            "product_code": package.job.template.code if package and package.job and package.job.template else None,
            "product_name": package.job.template.name if package and package.job and package.job.template else None,
            "project_code": package.job.project.project_code if package and package.job and package.job.project else None,
            "project_name": package.job.project.project_name if package and package.job and package.job.project else None,
            "destination_city": package.job.project.destination_city if package and package.job and package.job.project else None,
            "destination_site": package.job.project.site_name if package and package.job and package.job.project else None,
            "quantity": float(row.quantity), "status": row.status, "location_code": row.location.code,
            "gross_weight_kg": float(package.gross_weight_kg) if package and package.gross_weight_kg else None,
            "length_mm": float(package.job.template.length_mm) if package and package.job and package.job.template and package.job.template.length_mm else None,
            "width_mm": float(package.job.template.width_mm) if package and package.job and package.job.template and package.job.template.width_mm else None,
            "height_mm": float(package.job.template.height_mm) if package and package.job and package.job.template and package.job.template.height_mm else None,
            "version": row.version, "placed_at": row.placed_at,
        })
    return {"placements": items}


@router.get("/ready-for-logistics")
def ready_for_logistics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Canonical, derived logistics inbox; no copied registry or competing writer."""
    _dispatch(db, user)
    active_placement_ids = db.query(MesShipmentItem.placement_id).filter(
        MesShipmentItem.assignment_status == "active"
    )
    rows = db.query(MesFinishedGoodsPlacement).filter(
        MesFinishedGoodsPlacement.status == "placed",
        ~MesFinishedGoodsPlacement.id.in_(active_placement_ids),
    ).order_by(MesFinishedGoodsPlacement.project_id, MesFinishedGoodsPlacement.placed_at, MesFinishedGoodsPlacement.id).all()
    items = []
    projects = {}
    for row in rows:
        package = db.get(MesJobPackage, row.package_id) if row.package_id else None
        project = package.job.project if package and package.job else None
        item = {
            "id": row.id, "placement_id": row.id, "version": row.version,
            "project_id": row.project_id, "project_line_id": row.project_line_id,
            "release_id": row.release_id, "package_id": row.package_id,
            "package_number": package.package_number if package else None,
            "package_count": 1,
            "passport_serials": [passport.serial_number for passport in sorted(
                getattr(package, "product_passports", []), key=lambda passport: passport.unit_index
            )] if package else [],
            "project_code": project.project_code if project else f"#{row.project_id}",
            "project_name": project.project_name if project else "",
            "destination_city": project.destination_city if project else "",
            "destination_site": project.site_name if project else "",
            "destination_address": project.full_address if project else "",
            "product_code": package.job.template.code if package and package.job and package.job.template else None,
            "product_name": package.job.template.name if package and package.job and package.job.template else None,
            "quantity": float(row.quantity), "warehouse_state": row.status,
            "location_code": row.location.code, "assigned_trip_id": None,
            "gross_weight_kg": float(package.gross_weight_kg) if package and package.gross_weight_kg else None,
            "length_mm": float(package.job.template.length_mm) if package and package.job and package.job.template and package.job.template.length_mm else None,
            "width_mm": float(package.job.template.width_mm) if package and package.job and package.job.template and package.job.template.width_mm else None,
            "height_mm": float(package.job.template.height_mm) if package and package.job and package.job.template and package.job.template.height_mm else None,
        }
        if item["length_mm"] and item["width_mm"] and item["height_mm"]:
            item["volume_m3"] = round(item["length_mm"] * item["width_mm"] * item["height_mm"] / 1_000_000_000, 6)
        else:
            item["volume_m3"] = None
        items.append(item)
        bucket = projects.setdefault(row.project_id, {
            "project_id": row.project_id, "project_code": item["project_code"],
            "project_name": item["project_name"], "destination_city": item["destination_city"],
            "destination_site": item["destination_site"], "package_count": 0,
            "quantity": 0.0, "known_weight_kg": 0.0, "unknown_weight_count": 0,
        })
        bucket["package_count"] += 1
        bucket["quantity"] = round(bucket["quantity"] + item["quantity"], 4)
        if item["gross_weight_kg"] is None:
            bucket["unknown_weight_count"] += 1
        else:
            bucket["known_weight_kg"] = round(bucket["known_weight_kg"] + item["gross_weight_kg"], 4)
    return {"items": items, "projects": list(projects.values()), "totals": {
        "package_count": len(items), "project_count": len(projects),
        "quantity": round(sum(item["quantity"] for item in items), 4),
        "known_weight_kg": round(sum(item["gross_weight_kg"] or 0 for item in items), 4),
        "unknown_weight_count": sum(item["gross_weight_kg"] is None for item in items),
    }}


@router.post("/vehicles", status_code=201)
def vehicle_create(data: VehicleCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_vehicle_manage")
    try:
        row = create_vehicle(db, data, user.username); db.commit(); return _vehicle(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.get("/vehicles")
def vehicle_list(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    query = db.query(MesVehicle)
    if not include_inactive: query = query.filter(MesVehicle.is_active.is_(True))
    return {"vehicles": [_vehicle(row) for row in query.order_by(MesVehicle.registration_number).all()]}



@router.get("/driver/me")
def driver_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "driver":
        raise HTTPException(
            403,
            detail={"code": "driver_only"},
        )

    driver = serialize_driver(db, user)

    active_statuses = [
        "planned",
        "loading",
        "loaded",
        "dispatched",
        "in_transit",
        "arrived",
        "delivered",
    ]

    trip = (
        db.query(MesTrip)
        .filter(
            MesTrip.driver_user_id == user.id,
            MesTrip.status.in_(active_statuses),
        )
        .order_by(MesTrip.id.desc())
        .first()
    )

    device = (
        db.query(MesGpsDevice)
        .filter(
            MesGpsDevice.driver_user_id == user.id,
            MesGpsDevice.status == "active",
        )
        .order_by(MesGpsDevice.id.desc())
        .first()
    )

    vehicle_id = None
    if trip and trip.vehicle_id:
        vehicle_id = trip.vehicle_id
    elif device and device.vehicle_id:
        vehicle_id = device.vehicle_id

    vehicle = (
        db.query(MesVehicle)
        .filter(MesVehicle.id == vehicle_id)
        .first()
        if vehicle_id
        else None
    )

    gps = None
    if device:
        gps = {
            **serialize_device(device),
            "last_latitude": device.last_latitude,
            "last_longitude": device.last_longitude,
            "last_speed_kmh": device.last_speed_kmh,
            "last_heading_deg": device.last_heading_deg,
            "last_seen_at": device.last_seen_at,
            "last_captured_at": device.last_captured_at,
        }

    return {
        "driver": driver,
        "vehicle": _vehicle(vehicle) if vehicle else None,
        "gps_device": gps,
        "active_trip": _trip(trip) if trip else None,
    }


@router.get("/drivers")
def driver_list(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    query = db.query(User).filter(User.role == "driver")
    if not include_inactive:
        query = query.filter(User.is_active.is_(True))
    return {"drivers": [serialize_driver(db, row) for row in query.order_by(User.username).all()]}


@router.post("/drivers", status_code=201)
def driver_create(data: DriverCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_driver_manage")
    try:
        row = create_driver(db, data, user.username); db.commit(); return serialize_driver(db, row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.put("/drivers/{driver_id}")
def driver_update(driver_id: int, data: DriverUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_driver_manage")
    try:
        row = update_driver(db, driver_id, data, user.username); db.commit(); return serialize_driver(db, row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.post("/drivers/{driver_id}/status")
def driver_status(driver_id: int, data: DriverStatusUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_driver_manage")
    try:
        row = set_driver_status(db, driver_id, data.active, user.username); db.commit(); return serialize_driver(db, row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.get("/gps-devices")
def gps_device_list(include_inactive: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _view = user.role in ("admin", "super_admin") or user_has_permission(db, user, "gps_trip_view") or user_has_permission(db, user, "mes_terminal_dispatch")
    if not _view:
        raise HTTPException(403, detail={"code": "permission_denied"})
    query = db.query(MesGpsDevice)
    if not include_inactive:
        query = query.filter(MesGpsDevice.status == "active")
    return {"devices": [serialize_device(row) for row in query.order_by(MesGpsDevice.device_identifier).all()]}


@router.post("/gps-devices", status_code=201)
def gps_device_create(data: GpsDeviceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_gps_bind")
    try:
        row = create_gps_device(db, data, user.username); db.commit(); return serialize_device(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.put("/gps-devices/{device_id}")
def gps_device_update(device_id: int, data: GpsDeviceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_gps_bind")
    try:
        row = update_gps_device(db, device_id, data, user.username); db.commit(); return serialize_device(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.post("/gps-devices/{device_id}/unbind")
def gps_device_unbind(device_id: int, data: GpsDeviceUnbind, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_gps_bind")
    try:
        row = unbind_gps_device(db, device_id, data.expected_version, user.username); db.commit(); return serialize_device(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.put("/vehicles/{vehicle_id}")
def vehicle_update(vehicle_id: int, data: VehicleUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_vehicle_manage")
    row = db.query(MesVehicle).with_for_update().filter_by(id=vehicle_id).first()
    if not row: raise HTTPException(404, detail={"code": "vehicle_not_found"})
    try:
        row = update_vehicle(db, row, data, user.username); db.commit(); return _vehicle(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.put("/vehicles/{vehicle_id}/operational-state")
def vehicle_state_update(vehicle_id: int, data: VehicleStateUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _manage(db, user, "logistics_vehicle_manage")
    try:
        row = update_vehicle_state(db, vehicle_id, operational_state=data.operational_state,
                                   expected_version=data.expected_version, actor=user.username)
        db.commit(); return _vehicle(row)
    except LogisticsPlanningError as exc:
        db.rollback(); _planning_error(exc)


@router.post("/trips", status_code=201)
def trip_create(data: TripCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        row = create_trip(db, data, user.username); db.commit(); return _trip(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.post("/trips/consolidated", status_code=201)
def consolidated_trip_create(data: ConsolidatedTripCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        result = create_consolidated_trip(db, data, user.username)
        db.commit()
        return result
    except (ShipmentError, LogisticsError) as exc:
        db.rollback()
        if isinstance(exc, ShipmentError):
            _shipment_error(exc)
        _error(exc)


@router.get("/trips")
def trip_list(project_id: int | None = None, status: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    query = db.query(MesTrip)
    if project_id is not None:
        query = query.filter(or_(
            MesTrip.project_id == project_id,
            MesTrip.shipment_items.any(MesShipmentItem.project_id == project_id),
        ))
    if status: query = query.filter(MesTrip.status == status.strip().lower())
    return {"trips": [_trip(row) for row in query.order_by(MesTrip.created_at.desc()).all()]}


@router.get("/trips/{trip_id}")
def trip_detail(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _trip_operator(db, user, trip_id)
    payload = _trip(row)
    payload["dispatch_ids"] = [dispatch.id for dispatch in row.dispatches]
    payload["evidence"] = [_evidence(item) for item in sorted(row.evidence, key=lambda item: (item.occurred_at, item.id))]
    payload["alerts"] = derive_trip_alerts(db, row)
    payload["automatic_arrival"] = automatic_arrival_readiness(row)
    return payload

@router.get("/trips/{trip_id}/route")
def trip_route_get(trip_id:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _trip_operator(db,user,trip_id)
    try:return {"route":serialize_route(get_route(db,trip_id))}
    except TripRouteError as exc:_route_error(exc)

@router.post("/trips/{trip_id}/route",status_code=201)
def trip_route_create(trip_id:int,data:TripRouteCreate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        row=create_route(db,trip_id,data,user.username);db.commit();return serialize_route(row)
    except TripRouteError as exc:db.rollback();_route_error(exc)

@router.put("/trips/{trip_id}/route")
def trip_route_update(trip_id:int,data:TripRouteUpdate,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        row=get_route(db,trip_id)
        if not row:raise TripRouteError("route_not_found","Route not found",404)
        row=update_route(db,row,data,user.username);db.commit();return serialize_route(row)
    except TripRouteError as exc:db.rollback();_route_error(exc)

@router.post("/trips/{trip_id}/route/status")
def trip_route_status(trip_id:int,data:TripRouteStatus,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        row=get_route(db,trip_id)
        if not row:raise TripRouteError("route_not_found","Route not found",404)
        row=set_status(db,row,data.status,data.expected_version,user.username);db.commit();return serialize_route(row)
    except TripRouteError as exc:db.rollback();_route_error(exc)

@router.delete("/trips/{trip_id}/route")
def trip_route_cancel(trip_id:int,expected_version:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        row=get_route(db,trip_id)
        if not row:raise TripRouteError("route_not_found","Route not found",404)
        row=set_status(db,row,"cancelled",expected_version,user.username);db.commit();return serialize_route(row)
    except TripRouteError as exc:db.rollback();_route_error(exc)

@router.post("/trips/{trip_id}/route/stops",status_code=201)
def trip_route_stop_add(trip_id:int,data:TripRouteStopInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        route=get_route(db,trip_id)
        if not route:raise TripRouteError("route_not_found","Route not found",404)
        if route.version!=data.expected_version:raise TripRouteError("route_version_conflict","Route was changed by another user",409)
        add_stop(db,route,data,user.username);db.commit();return serialize_route(route)
    except TripRouteError as exc:db.rollback();_route_error(exc)

@router.put("/trips/{trip_id}/route/stops/{stop_id}")
def trip_route_stop_update(trip_id:int,stop_id:int,data:TripRouteStopInput,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        route=get_route(db,trip_id);stop=db.get(MesTripRouteStop,stop_id)
        if not route or not stop or stop.route_id!=route.id:raise TripRouteError("route_stop_not_found","Route stop not found",404)
        update_stop(db,route,stop,data,user.username);db.commit();return serialize_route(route)
    except TripRouteError as exc:db.rollback();_route_error(exc)

@router.delete("/trips/{trip_id}/route/stops/{stop_id}")
def trip_route_stop_delete(trip_id:int,stop_id:int,expected_version:int,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        route=get_route(db,trip_id);stop=db.get(MesTripRouteStop,stop_id)
        if not route or not stop or stop.route_id!=route.id:raise TripRouteError("route_stop_not_found","Route stop not found",404)
        delete_stop(db,route,stop,expected_version,user.username);db.commit();return serialize_route(route)
    except TripRouteError as exc:db.rollback();_route_error(exc)

@router.post("/trips/{trip_id}/route/stops/reorder")
def trip_route_stop_reorder(trip_id:int,data:TripRouteReorder,db:Session=Depends(get_db),user:User=Depends(get_current_user)):
    _dispatch(db,user)
    try:
        route=get_route(db,trip_id)
        if not route:raise TripRouteError("route_not_found","Route not found",404)
        reorder_stops(db,route,data.stop_ids,data.expected_version,user.username);db.commit();return serialize_route(route)
    except TripRouteError as exc:db.rollback();_route_error(exc)


@router.put("/trips/{trip_id}/assignment")
def trip_assignment_update(trip_id: int, data: TripAssignmentUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        row = update_trip_assignment(db, trip_id, vehicle_id=data.vehicle_id,
                                     driver_user_id=data.driver_user_id,
                                     expected_version=data.expected_version, actor=user.username)
        db.commit(); return _trip(row)
    except LogisticsPlanningError as exc:
        db.rollback(); _planning_error(exc)


@router.put("/trips/{trip_id}/planning")
def trip_planning_update(trip_id: int, data: TripPlanningUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        row = update_trip_plan(db, trip_id, planned_loading_at=data.planned_loading_at,
                               planned_departure_at=data.planned_departure_at,
                               delivery_deadline_at=data.delivery_deadline_at,
                               expected_version=data.expected_version, actor=user.username)
        db.commit(); return _trip(row)
    except LogisticsPlanningError as exc:
        db.rollback(); _planning_error(exc)


@router.get("/alerts")
def logistics_alerts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    trips = db.query(MesTrip).filter(MesTrip.status.in_(CONFLICTING_TRIP_STATUSES)).all()
    return {"alerts": [alert for trip in trips for alert in derive_trip_alerts(db, trip)]}


@router.post("/trips/{trip_id}/dispatches/{dispatch_id}")
def trip_attach_dispatch(trip_id: int, dispatch_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip: raise HTTPException(404, detail={"code": "trip_not_found"})
    try:
        row = attach_dispatch(db, trip, dispatch_id, user.username); db.commit()
        return {"trip_id": trip.id, "dispatch_id": row.id}
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.post("/trips/{trip_id}/transition")
def trip_transition(trip_id: int, data: TripTransition, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    trip = db.query(MesTrip).with_for_update().filter_by(id=trip_id).first()
    if not trip: raise HTTPException(404, detail={"code": "trip_not_found"})
    try:
        row = transition_trip(db, trip, data.status, data.expected_version, user.username); db.commit(); return _trip(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.post("/trips/{trip_id}/shipment-items", status_code=201)
def shipment_item_assign(trip_id: int, data: ShipmentAssign, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        result = assign_placement(db, trip_id, data.placement_id, dispatch_id=data.dispatch_id,
                                  planned_quantity=data.planned_quantity, idempotency_key=data.idempotency_key,
                                  actor=user.username)
        db.commit(); return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.delete("/trips/{trip_id}/shipment-items/{item_id}")
def shipment_item_remove(trip_id: int, item_id: int, expected_version: int,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        remove_assignment(db, trip_id, item_id, expected_version, user.username); db.commit()
        return {"removed": True, "item_id": item_id}
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.get("/trips/{trip_id}/load-corrections")
def load_correction_list(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = _trip_operator(db, user, trip_id)
    return {"trip_id": trip.id, "corrections": correction_history(db, trip.id)}


@router.post("/trips/{trip_id}/shipment-items/{item_id}/unload")
def load_correction_unload(trip_id: int, item_id: int, data: LoadCorrectionRequest,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip:
        raise HTTPException(404, detail={"code": "trip_not_found"})
    _loading_correction_permission(db, user, trip)
    try:
        result = unload_package(
            db, trip_id, item_id, expected_trip_version=data.expected_trip_version,
            expected_item_version=data.expected_item_version, reason=data.reason,
            notes=data.notes, idempotency_key=data.idempotency_key, actor=user.username,
        )
        db.commit()
        return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/shipment-items/{item_id}/return-to-warehouse")
def load_correction_return(trip_id: int, item_id: int, data: LoadCorrectionRequest,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip:
        raise HTTPException(404, detail={"code": "trip_not_found"})
    _loading_correction_permission(db, user, trip)
    try:
        result = return_to_warehouse(
            db, trip_id, item_id, expected_trip_version=data.expected_trip_version,
            expected_item_version=data.expected_item_version, reason=data.reason,
            notes=data.notes, idempotency_key=data.idempotency_key, actor=user.username,
        )
        db.commit()
        return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/shipment-items/{item_id}/reload")
def load_correction_reload(trip_id: int, item_id: int, data: LoadCorrectionRequest,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip:
        raise HTTPException(404, detail={"code": "trip_not_found"})
    _loading_correction_permission(db, user, trip)
    try:
        result = reload_package(
            db, trip_id, item_id, expected_trip_version=data.expected_trip_version,
            expected_item_version=data.expected_item_version, reason=data.reason,
            notes=data.notes, idempotency_key=data.idempotency_key, actor=user.username,
        )
        db.commit()
        return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/shipment-items/{item_id}/transfer")
def load_correction_transfer(trip_id: int, item_id: int, data: LoadTransferRequest,
                             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip:
        raise HTTPException(404, detail={"code": "trip_not_found"})
    _loading_correction_permission(db, user, trip, transfer=True)
    try:
        result = transfer_package(
            db, trip_id, item_id, target_trip_id=data.target_trip_id,
            expected_trip_version=data.expected_trip_version,
            expected_target_trip_version=data.expected_target_trip_version,
            expected_item_version=data.expected_item_version, reason=data.reason,
            notes=data.notes, idempotency_key=data.idempotency_key, actor=user.username,
        )
        db.commit()
        return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/shipment-items/{item_id}/replace")
def load_correction_replace(trip_id: int, item_id: int, data: LoadReplaceRequest,
                            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip:
        raise HTTPException(404, detail={"code": "trip_not_found"})
    _loading_correction_permission(db, user, trip)
    try:
        result = replace_package(
            db, trip_id, item_id, replacement_placement_id=data.replacement_placement_id,
            expected_trip_version=data.expected_trip_version,
            expected_item_version=data.expected_item_version,
            expected_replacement_version=data.expected_replacement_version,
            reason=data.reason, notes=data.notes, idempotency_key=data.idempotency_key,
            actor=user.username,
        )
        db.commit()
        return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.get("/trips/{trip_id}/loading-plan")
def loading_plan_read(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip: raise HTTPException(404, detail={"code": "trip_not_found"})
    try:
        validation = validate_plan(db, trip, require_complete=False)
        return {"trip_id": trip.id, "placements": [serialize_plan(row) for row in sorted(trip.loading_plan, key=lambda row: row.loading_sequence)], "totals": validation}
    except ShipmentError as exc:
        _shipment_error(exc)


@router.put("/trips/{trip_id}/loading-plan")
def loading_plan_update(trip_id: int, data: PlanUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        result = save_plan(db, trip_id, [row.model_dump() for row in data.placements], user.username)
        db.commit(); return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/loading-plan/automatic")
def loading_plan_automatic(trip_id: int, persist: bool = False,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip: raise HTTPException(404, detail={"code": "trip_not_found"})
    try:
        result = automatic_initial_plan(db, trip)
        if persist and result["placements"]:
            result["saved_totals"] = save_plan(db, trip.id, result["placements"], user.username)
            db.commit()
        return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/loading-plan/validate")
def loading_plan_validate(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip: raise HTTPException(404, detail={"code": "trip_not_found"})
    try: return validate_plan(db, trip, require_complete=True)
    except ShipmentError as exc: _shipment_error(exc)


@router.post("/trips/{trip_id}/confirm-loading")
def loading_confirm(trip_id: int, data: LoadingConfirm, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        result = confirm_loading(db, trip_id, acknowledge_unknown_weight=data.acknowledge_unknown_weight,
                                 idempotency_key=data.idempotency_key, actor=user.username)
        db.commit(); return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/dispatch")
def trip_dispatch_execute(trip_id: int, data: CommandRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        result = final_dispatch(db, trip_id, idempotency_key=data.idempotency_key, actor=user.username)
        db.commit(); return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/arrival")
def trip_arrival_confirm(trip_id: int, data: ArrivalRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _trip_operator(db, user, trip_id)
    try:
        result = confirm_arrival(db, trip_id, expected_version=data.expected_version,
                                 idempotency_key=data.idempotency_key, actor=user.username)
        db.commit(); return result
    except TripLifecycleError as exc:
        db.rollback(); raise HTTPException(exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


@router.post("/trips/{trip_id}/delivery")
def trip_delivery_execute(trip_id: int, data: DeliveryRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _trip_operator(db, user, trip_id)
    try:
        result = record_delivery(db, trip_id, [row.model_dump() for row in data.dispositions],
                                 idempotency_key=data.idempotency_key, actor=user.username)
        db.commit(); return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.post("/trips/{trip_id}/acceptance")
def trip_acceptance_execute(trip_id: int, data: AcceptanceRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    try:
        result = accept_delivery(db, trip_id, recipient_name=data.recipient_name, notes=data.notes,
                                 resolved_shortage_item_ids=data.resolved_shortage_item_ids,
                                 idempotency_key=data.idempotency_key, actor=user.username,
                                 project_id=data.project_id)
        db.commit(); return result
    except ShipmentError as exc:
        db.rollback(); _shipment_error(exc)


@router.get("/trips/{trip_id}/progress")
def trip_progress_endpoint(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    trip = db.query(MesTrip).filter_by(id=trip_id).first()
    if not trip: raise HTTPException(404, detail={"code": "trip_not_found"})
    return trip_progress(db, trip)


@router.get("/trips/{trip_id}/documents")
def trip_document_list(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _trip_operator(db, user, trip_id)
    rows = db.query(MesTripDocumentSnapshot).filter_by(trip_id=trip_id).order_by(
        MesTripDocumentSnapshot.document_type, MesTripDocumentSnapshot.version.desc()).all()
    return {"documents": [{"id": row.id, "document_type": row.document_type, "version": row.version,
                            "filename": row.original_filename, "file_size": row.file_size,
                            "checksum": row.checksum, "generated_by": row.generated_by,
                            "generated_at": row.generated_at} for row in rows]}


@router.post("/trips/{trip_id}/documents", status_code=201)
def trip_document_generate(trip_id: int, data: TripDocumentCreate, db: Session = Depends(get_db),
                           user: User = Depends(get_current_user)):
    _dispatch(db, user)
    if data.document_type not in DOCUMENT_TYPES:
        raise HTTPException(422, detail={"code": "unsupported_document_type"})
    try:
        row = generate_trip_document(db, trip_id, data.document_type, user.username, data.language)
        log_action(db, user.username, "generate_trip_document", "mes_trip", trip_id,
                   f"document_type={row.document_type}; version={row.version}; checksum={row.checksum}")
        db.commit()
        return {"id": row.id, "document_type": row.document_type, "version": row.version,
                "filename": row.original_filename, "file_size": row.file_size, "checksum": row.checksum}
    except ValueError as exc:
        db.rollback()
        code = str(exc)
        raise HTTPException(404 if code == "trip_not_found" else 422, detail={"code": code}) from exc


@router.get("/trip-documents/{document_id}/download")
def trip_document_download(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.get(MesTripDocumentSnapshot, document_id)
    if not row:
        raise HTTPException(404, detail={"code": "document_not_found"})
    _trip_operator(db, user, row.trip_id)
    try:
        path = document_path(row)
    except ValueError as exc:
        raise HTTPException(404, detail={"code": "document_not_found"}) from exc
    return FileResponse(path, media_type=row.mime_type, filename=row.original_filename)


@router.get("/trips/{trip_id}/evidence")
def evidence_list(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _trip_operator(db, user, trip_id)
    rows = db.query(MesTripEvidence).filter_by(trip_id=trip_id).order_by(MesTripEvidence.occurred_at, MesTripEvidence.id).all()
    return {"evidence": [_evidence(row) for row in rows]}


@router.post("/trips/{trip_id}/evidence", status_code=201)
async def evidence_upload(trip_id: int, evidence_type: str = Form(...), note: str = Form(""),
                          latitude: float | None = Form(None), longitude: float | None = Form(None),
                          file: UploadFile = File(...), db: Session = Depends(get_db),
                          user: User = Depends(get_current_user)):
    trip = _trip_operator(db, user, trip_id)
    content = await file.read()
    try:
        row = save_trip_evidence(db, trip=trip, evidence_type=evidence_type, content=content,
                                 original_filename=file.filename or "evidence", claimed_mime=file.content_type or "",
                                 actor=user.username, note=note, latitude=latitude, longitude=longitude)
        db.commit(); return _evidence(row)
    except LogisticsError as exc:
        db.rollback(); _error(exc)


@router.get("/evidence/{evidence_id}/download")
def evidence_download(evidence_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _dispatch(db, user)
    row = db.query(MesTripEvidence).filter_by(id=evidence_id).first()
    if not row: raise HTTPException(404, detail={"code": "evidence_not_found"})
    try: path = evidence_path(row)
    except LogisticsError as exc: _error(exc)
    if not path.is_file(): raise HTTPException(404, detail={"code": "evidence_file_missing"})
    log_action(db, user.username, "download", "mes_trip_evidence", row.id, f"trip={row.trip_id}")
    db.commit()
    return FileResponse(path, media_type=row.mime_type, filename=row.original_filename)
