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
from models import ChatMessage, ChatReadState, ChatRoom, Driver, TransportTask, User, Vehicle
from routers.auth_router import _authenticate_user, _login_candidates_for_phone, _normalize_phone_digits
from routers.gps_router import _serialize_transport_task, latest_locations_by_vehicle
from schemas import PhoneLoginRequest, TokenResponse
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


@router.get("/tasks")
def driver_tasks(
    status: str = Query(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    driver = _require_driver(db, user)
    query = (
        db.query(TransportTask)
        .options(joinedload(TransportTask.vehicle), joinedload(TransportTask.driver))
        .filter(TransportTask.driver_id == driver.id)
        .order_by(desc(TransportTask.created_at))
    )
    if status:
        query = query.filter(TransportTask.status == status)
    tasks = query.limit(100).all()
    latest = latest_locations_by_vehicle(db)
    return {
        "driver": _serialize_driver(driver),
        "tasks": [
            _serialize_transport_task(t, latest.get(t.vehicle_id) if t.vehicle_id else None)
            for t in tasks
        ],
    }


@router.post("/tasks/{task_id}/start")
def driver_start_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    driver = _require_driver(db, user)
    task = db.query(TransportTask).filter(TransportTask.id == task_id).first()
    if not task or task.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.vehicle_id:
        raise HTTPException(status_code=400, detail="Assign a vehicle first")
    task.tracking_active = True
    task.status = "active"
    task.started_at = task.started_at or datetime.utcnow()
    driver.status = "on_trip"
    db.commit()
    task = (
        db.query(TransportTask)
        .options(joinedload(TransportTask.vehicle), joinedload(TransportTask.driver))
        .filter(TransportTask.id == task_id)
        .first()
    )
    loc = latest_locations_by_vehicle(db).get(task.vehicle_id)
    return _serialize_transport_task(task, loc)


@router.post("/tasks/{task_id}/complete")
def driver_complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    driver = _require_driver(db, user)
    task = db.query(TransportTask).filter(TransportTask.id == task_id).first()
    if not task or task.driver_id != driver.id:
        raise HTTPException(status_code=404, detail="Task not found")
    task.tracking_active = False
    task.status = "completed"
    task.completed_at = datetime.utcnow()
    if driver.status == "on_trip":
        driver.status = "active"
    db.commit()
    task = (
        db.query(TransportTask)
        .options(joinedload(TransportTask.vehicle), joinedload(TransportTask.driver))
        .filter(TransportTask.id == task_id)
        .first()
    )
    loc = latest_locations_by_vehicle(db).get(task.vehicle_id) if task.vehicle_id else None
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
