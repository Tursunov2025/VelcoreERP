"""Velcore Driver mobile — login, tasks, chat, photo upload."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from auth.deps import get_current_user
from auth.security import AuthNotConfiguredError, create_access_token, create_refresh_token
from config.paths import UPLOAD_PATH
from database import get_db
from models import ChatMessage, ChatReadState, ChatRoom, Driver, TransportTask, TransportTaskEvent, User, Vehicle
from routers.auth_router import _authenticate_user, _login_candidates_for_phone, _normalize_phone_digits
from routers.gps_router import _serialize_transport_task, latest_locations_by_vehicle
from schemas import DriverCodeLoginRequest, PhoneLoginRequest, TokenResponse
from services.audit import log_action

router = APIRouter(prefix="/driver", tags=["driver"])

DRIVER_CHAT_ROOM_NAME = "Velcore Haydovchilar"
DRIVER_TYPES = ("internal", "external")
DRIVER_PHOTO_DIR = UPLOAD_PATH / "driver_photos"
DRIVER_PHOTO_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_SIZE = 8 * 1024 * 1024


class DriverLoginResponse(TokenResponse):
    driver: dict | None = None
    vehicle: dict | None = None


class DriverMessageIn(BaseModel):
    content: str = ""
    attachment_url: str | None = None


def _token_response(user: User) -> TokenResponse:
    dept = user.department or ("Admin" if user.role == "admin" else "Logistika")
    data = {"sub": user.username, "role": user.role, "department": dept}
    try:
        return TokenResponse(
            access_token=create_access_token(data),
            refresh_token=create_refresh_token(data),
            username=user.username,
            role=user.role,
            department=dept,
        )
    except AuthNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def _serialize_driver(d: Driver) -> dict:
    return {
        "id": d.id,
        "full_name": d.full_name,
        "phone": d.phone,
        "status": d.status,
        "driver_type": getattr(d, "driver_type", None) or "internal",
        "user_username": getattr(d, "user_username", None) or "",
        "default_vehicle_id": getattr(d, "default_vehicle_id", None),
    }


def _serialize_vehicle(v: Vehicle | None) -> dict | None:
    if not v:
        return None
    return {"id": v.id, "plate_number": v.plate_number, "model": v.model, "status": v.status}


def _find_driver_for_user(db: Session, user: User) -> Driver | None:
    linked = (
        db.query(Driver)
        .filter(Driver.user_username == user.username)
        .order_by(Driver.id)
        .first()
    )
    if linked:
        return linked

    digits = _normalize_phone_digits(user.username)
    if not digits:
        return None

    candidates = {digits}
    if len(digits) == 9:
        candidates.add(f"998{digits}")
    elif digits.startswith("998") and len(digits) >= 12:
        candidates.add(digits[3:])

    drivers = db.query(Driver).all()
    for d in drivers:
        phone_digits = _normalize_phone_digits(d.phone)
        if not phone_digits:
            continue
        for c in candidates:
            if phone_digits == c or phone_digits.endswith(c) or c.endswith(phone_digits):
                return d
            if len(phone_digits) >= 9 and len(c) >= 9 and phone_digits[-9:] == c[-9:]:
                return d
    return None


def _require_driver(db: Session, user: User) -> Driver:
    driver = _find_driver_for_user(db, user)
    if not driver:
        raise HTTPException(
            status_code=403,
            detail="Haydovchi profili topilmadi. ERP da Driver yozuvi va telefon bog'lanishini tekshiring.",
        )
    if driver.status == "inactive":
        raise HTTPException(status_code=403, detail="Haydovchi hisobi faol emas")
    return driver


def _get_or_create_driver_room(db: Session) -> ChatRoom:
    room = db.query(ChatRoom).filter(ChatRoom.name == DRIVER_CHAT_ROOM_NAME).first()
    if room:
        return room
    room = ChatRoom(
        name=DRIVER_CHAT_ROOM_NAME,
        room_type="department",
        department="Logistika",
        created_by="system",
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def _can_access_driver_room(user: User, driver: Driver | None) -> bool:
    if user.role == "admin" or user.department in ("Admin", "Logistika"):
        return True
    return driver is not None


def _serialize_chat_message(msg: ChatMessage) -> dict:
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "sender_username": msg.sender_username,
        "sender_department": msg.sender_department,
        "content": msg.content,
        "message_type": msg.message_type,
        "attachment_url": msg.attachment_url,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }


@router.post("/login", response_model=DriverLoginResponse)
def driver_login(data: PhoneLoginRequest, db: Session = Depends(get_db)):
    """Telefon + parol — haydovchi mobil ilova."""
    candidates = _login_candidates_for_phone(data.phone)
    if not candidates:
        raise HTTPException(status_code=400, detail="Telefon raqam noto'g'ri")

    user = None
    for username in candidates:
        user = _authenticate_user(db, username, data.password)
        if user:
            break
    if not user:
        raise HTTPException(status_code=401, detail="Telefon yoki parol xato")

    driver = _find_driver_for_user(db, user)
    vehicle = None
    if driver and getattr(driver, "default_vehicle_id", None):
        vehicle = db.query(Vehicle).filter(Vehicle.id == driver.default_vehicle_id).first()

    if driver and not getattr(driver, "user_username", None):
        driver.user_username = user.username
        db.commit()

    base = _token_response(user)
    log_action(db, user.username, "driver_login", f"driver={driver.id if driver else 'none'}")
    return DriverLoginResponse(
        **base.model_dump(),
        driver=_serialize_driver(driver) if driver else None,
        vehicle=_serialize_vehicle(vehicle),
    )


@router.post("/login/code", response_model=DriverLoginResponse)
def driver_login_code(
    data: DriverCodeLoginRequest,
    db: Session = Depends(get_db),
):
    """Driver code + password login."""
    code = (data.login_code or "").strip().upper()

    if not code:
        raise HTTPException(status_code=400, detail="Login kodi kerak")

    driver = (
        db.query(Driver)
        .filter(Driver.login_code == code)
        .first()
    )

    if not driver:
        raise HTTPException(status_code=401, detail="Login kodi yoki parol xato")

    if (driver.status or "active").lower() not in {"active", "on_trip"}:
        raise HTTPException(status_code=403, detail="Haydovchi faol emas")

    password_hash = getattr(driver, "password_hash", "") or ""
    if not password_hash:
        raise HTTPException(status_code=401, detail="Driver paroli sozlanmagan")

    from auth.security import verify_password

    if not verify_password(data.password, password_hash):
        raise HTTPException(status_code=401, detail="Login kodi yoki parol xato")

    username = (driver.user_username or "").strip()
    if not username:
        raise HTTPException(status_code=403, detail="Driver ERP foydalanuvchisiga ulanmagan")

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status_code=403, detail="ERP foydalanuvchisi faol emas")

    base = _token_response(user)

    vehicle = None
    if getattr(driver, "default_vehicle_id", None):
        vehicle = (
            db.query(Vehicle)
            .filter(Vehicle.id == driver.default_vehicle_id)
            .first()
        )

    log_action(
        db,
        user.username,
        "driver_login_code",
        f"driver={driver.id}",
    )

    return DriverLoginResponse(
        **base.model_dump(),
        driver=_serialize_driver(driver),
        vehicle=_serialize_vehicle(vehicle),
    )


class DriverTaskLocationIn(BaseModel):
    latitude: float | None = None
    longitude: float | None = None
    address: str = ""


@router.get("/tasks")
def driver_tasks(
    status: str = Query(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "driver":
        raise HTTPException(status_code=403, detail="Driver access required")

    query = (
        db.query(TransportTask)
        .options(
            joinedload(TransportTask.vehicle),
            joinedload(TransportTask.driver),
        )
        .filter(TransportTask.driver_user_id == user.id)
        .order_by(desc(TransportTask.created_at))
    )

    if status:
        query = query.filter(TransportTask.status == status)

    tasks = query.limit(100).all()
    latest = latest_locations_by_vehicle(db)

    return {
        "driver": {
            "id": user.id,
            "username": user.username,
            "full_name": getattr(user, "full_name", "") or user.username,
            "phone": getattr(user, "phone", "") or "",
        },
        "tasks": [
            _serialize_transport_task(
                t,
                latest.get(t.vehicle_id) if t.vehicle_id else None,
            )
            for t in tasks
        ],
    }


@router.post("/tasks/{task_id}/pickup")
def driver_pickup_task(
    task_id: int,
    data: DriverTaskLocationIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = (
        db.query(TransportTask)
        .filter(
            TransportTask.id == task_id,
            TransportTask.driver_user_id == user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "assigned":
        raise HTTPException(status_code=400, detail="Task yukni olish holatida emas")

    if not task.vehicle_id:
        raise HTTPException(status_code=400, detail="Taskga transport biriktirilmagan")

    now = datetime.utcnow()

    task.status = "picked_up"
    task.tracking_active = True
    task.picked_up_at = now
    task.started_at = task.started_at or now

    task.pickup_latitude = data.latitude
    task.pickup_longitude = data.longitude
    task.pickup_address = (data.address or "").strip()

    driver = _find_driver_for_user(db, user)
    if driver:
        driver.status = "on_trip"

    event = TransportTaskEvent(
        task_id=task.id,
        event_type="pickup",
        actor_user_id=user.id,
        actor_username=user.username,
        latitude=data.latitude,
        longitude=data.longitude,
        address=(data.address or "").strip(),
        note="Yuk haydovchi tomonidan olindi",
        created_at=now,
    )
    db.add(event)

    db.commit()
    db.refresh(task)

    log_action(
        db,
        user.username,
        "driver_task_pickup",
        f"task={task.id}",
    )

    loc = (
        latest_locations_by_vehicle(db).get(task.vehicle_id)
        if task.vehicle_id
        else None
    )

    return _serialize_transport_task(task, loc)


@router.post("/tasks/{task_id}/deliver")
async def driver_deliver_task(
    task_id: int,
    file: UploadFile = File(...),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
    address: str = Form(""),
    note: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    task = (
        db.query(TransportTask)
        .filter(
            TransportTask.id == task_id,
            TransportTask.driver_user_id == user.id,
        )
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "picked_up":
        raise HTTPException(status_code=400, detail="Avval yukni olish kerak")

    content_type = (file.content_type or "").split(";")[0].strip().lower()

    if content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Faqat JPEG, PNG yoki WebP",
        )

    data = await file.read()

    if len(data) > MAX_PHOTO_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Fayl hajmi 8 MB dan oshmasin",
        )

    ext = (
        ".jpg"
        if content_type == "image/jpeg"
        else ".png"
        if content_type == "image/png"
        else ".webp"
    )

    filename = f"task_{task_id}_{uuid.uuid4().hex}{ext}"
    path = DRIVER_PHOTO_DIR / filename
    path.write_bytes(data)

    now = datetime.utcnow()
    photo_url = f"/uploads/driver_photos/{filename}"
    clean_address = (address or "").strip()
    clean_note = (note or "").strip()

    task.status = "completed"
    task.tracking_active = False
    task.delivered_at = now
    task.completed_at = now

    task.delivery_latitude = latitude
    task.delivery_longitude = longitude
    task.delivery_address = clean_address

    task.completion_photo_url = photo_url
    task.completion_note = clean_note

    driver = _find_driver_for_user(db, user)
    if driver and driver.status == "on_trip":
        driver.status = "active"

    event = TransportTaskEvent(
        task_id=task.id,
        event_type="delivery",
        actor_user_id=user.id,
        actor_username=user.username,
        latitude=latitude,
        longitude=longitude,
        address=clean_address,
        photo_url=photo_url,
        note=clean_note,
        created_at=now,
    )
    db.add(event)

    db.commit()
    db.refresh(task)

    log_action(
        db,
        user.username,
        "driver_task_complete",
        f"task={task.id} photo={filename}",
    )

    loc = (
        latest_locations_by_vehicle(db).get(task.vehicle_id)
        if task.vehicle_id
        else None
    )

    return _serialize_transport_task(task, loc)


@router.get("/messages")
def driver_messages(
    since_id: int = Query(0),
    limit: int = Query(80, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    driver = _find_driver_for_user(db, user)
    if not _can_access_driver_room(user, driver):
        raise HTTPException(status_code=403, detail="Chat ruxsati yo'q")

    room = _get_or_create_driver_room(db)
    query = db.query(ChatMessage).filter(ChatMessage.room_id == room.id)
    if since_id:
        msgs = query.filter(ChatMessage.id > since_id).order_by(ChatMessage.id.asc()).limit(limit).all()
    else:
        msgs = list(reversed(query.order_by(desc(ChatMessage.id)).limit(limit).all()))

    state = (
        db.query(ChatReadState)
        .filter(ChatReadState.username == user.username, ChatReadState.room_id == room.id)
        .first()
    )
    if msgs:
        last_id = msgs[-1].id
        if not state:
            state = ChatReadState(username=user.username, room_id=room.id)
            db.add(state)
        state.last_read_message_id = max(state.last_read_message_id or 0, last_id)
        state.last_read_at = datetime.utcnow()
        db.commit()

    return {
        "room_id": room.id,
        "room_name": room.name,
        "messages": [_serialize_chat_message(m) for m in msgs],
    }


@router.post("/messages")
def driver_send_message(
    data: DriverMessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    driver = _require_driver(db, user)
    room = _get_or_create_driver_room(db)
    content = (data.content or "").strip()
    if not content and not data.attachment_url:
        raise HTTPException(status_code=400, detail="Empty message")

    sender_label = driver.full_name or user.username
    msg = ChatMessage(
        room_id=room.id,
        sender_username=user.username,
        sender_department=f"Haydovchi ({driver.driver_type})" if getattr(driver, "driver_type", None) else "Haydovchi",
        content=content or sender_label,
        message_type="image" if data.attachment_url else "text",
        attachment_url=data.attachment_url,
    )
    db.add(msg)
    db.flush()

    state = (
        db.query(ChatReadState)
        .filter(ChatReadState.username == user.username, ChatReadState.room_id == room.id)
        .first()
    )
    if not state:
        state = ChatReadState(username=user.username, room_id=room.id)
        db.add(state)
    state.last_read_message_id = msg.id
    state.last_read_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    log_action(db, user.username, "driver_message", f"room={room.id} msg={msg.id}")
    return {"message": _serialize_chat_message(msg)}


@router.post("/photo")
async def driver_upload_photo(
    file: UploadFile = File(...),
    caption: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Foto yuklash va chat xabariga biriktirish."""
    driver = _require_driver(db, user)
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail="Faqat JPEG, PNG yoki WebP")

    data = await file.read()
    if len(data) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="Fayl hajmi 8 MB dan oshmasin")

    ext = ".jpg" if "jpeg" in content_type else ".png" if "png" in content_type else ".webp"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = DRIVER_PHOTO_DIR / filename
    path.write_bytes(data)

    attachment_url = f"/uploads/driver_photos/{filename}"
    room = _get_or_create_driver_room(db)
    msg = ChatMessage(
        room_id=room.id,
        sender_username=user.username,
        sender_department=f"Haydovchi ({getattr(driver, 'driver_type', 'internal')})",
        content=(caption or "").strip() or f"Foto — {driver.full_name}",
        message_type="image",
        attachment_url=attachment_url,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    log_action(db, user.username, "driver_photo", f"file={filename}")
    return {
        "url": attachment_url,
        "message": _serialize_chat_message(msg),
    }


@router.get("/profile")
def driver_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    driver = _require_driver(db, user)
    vehicle = None
    if getattr(driver, "default_vehicle_id", None):
        vehicle = db.query(Vehicle).filter(Vehicle.id == driver.default_vehicle_id).first()
    return {"driver": _serialize_driver(driver), "vehicle": _serialize_vehicle(vehicle)}


@router.get("/drivers")
def list_driver_types(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Ichki (3) va tashqi (5) haydovchilar ro'yxati — admin/logistika."""
    if user.role != "admin" and user.department not in ("Admin", "Logistika"):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = db.query(Driver).order_by(Driver.driver_type, Driver.id).all()
    internal = [d for d in rows if (getattr(d, "driver_type", None) or "internal") == "internal"]
    external = [d for d in rows if getattr(d, "driver_type", None) == "external"]
    return {
        "internal": [_serialize_driver(d) for d in internal],
        "external": [_serialize_driver(d) for d in external],
        "limits": {"internal": 3, "external": 5},
    }
