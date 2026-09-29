"""Authoritative Digital Signage API for the canonical Display Center."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from config.paths import UPLOAD_PATH
from database import get_db
from models import (
    Display, DisplayHeartbeat, DisplayMediaAsset, DisplayPlaylist,
    DisplayPlaylistItem, DisplaySchedule, DisplayTemplate, DisplayWidget, User,
)
from services.display_center import (
    BUILT_IN_WIDGET_TYPES, DISPLAY_SETTINGS_DEFAULTS, TEMPLATE_KEYS, dashboard,
    effective_display_status, record_heartbeat, runtime_payload, serialize,
)
from services.display_center_data_provider import factory_dashboard
from services.permissions import user_has_permission
from services.platform_administration import append_audit, get_versioned_setting, put_versioned_setting

router = APIRouter(prefix="/display-center", tags=["display-center"])
MEDIA_ROOT = UPLOAD_PATH / "display-center"
MAX_MEDIA_BYTES = 25 * 1024 * 1024


def require_display(permission: str):
    def dependency(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
        if user.role != "super_admin" and not user_has_permission(db, user, permission):
            raise HTTPException(403, {"code": "permission_denied", "message": f"Permission required: {permission}"})
        return user
    return dependency


def _audit_context(request: Request) -> dict[str, str]:
    return {"ip_address": request.client.host if request.client else "", "correlation_id": request.headers.get("x-request-id", "")[:128]}


class DisplayIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
    location: str = Field(default="", max_length=255)
    description: str = Field(default="", max_length=2000)
    ip_address: str = Field(default="", max_length=64)
    resolution: str = Field(default="1920x1080", pattern=r"^\d{2,5}x\d{2,5}$")
    orientation: Literal["landscape", "portrait"] = "landscape"
    playlist_id: int | None = None
    is_active: bool = True


class WidgetIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,79}$")
    name: str = Field(min_length=2, max_length=160)
    widget_type: str
    settings_json: dict = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("widget_type")
    @classmethod
    def supported_widget(cls, value: str) -> str:
        if value not in BUILT_IN_WIDGET_TYPES:
            raise ValueError("Unsupported widget type")
        return value


class PlaylistIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default="", max_length=2000)
    template_key: str = Field(default="custom", max_length=64)
    template_id: int | None = None
    is_active: bool = True


class TemplateIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(default="factory", max_length=64)
    canvas_json: dict = Field(default_factory=lambda: {"width": 1920, "height": 1080, "grid": 20})
    layout_json: dict = Field(default_factory=lambda: {"widgets": []})
    is_active: bool = True

    @model_validator(mode="after")
    def validate_canvas(self):
        width = int(self.canvas_json.get("width", 0) or 0)
        height = int(self.canvas_json.get("height", 0) or 0)
        widgets = self.layout_json.get("widgets", [])
        if not 320 <= width <= 7680 or not 240 <= height <= 4320:
            raise ValueError("Canvas dimensions are outside the supported range")
        if not isinstance(widgets, list) or len(widgets) > 200:
            raise ValueError("Template widgets must be a list with at most 200 items")
        return self


class TemplateCloneIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)


class PlaylistItemIn(BaseModel):
    item_type: str = Field(min_length=2, max_length=32)
    widget_id: int | None = None
    media_id: int | None = None
    settings_json: dict = Field(default_factory=dict)
    position: int = Field(default=0, ge=0, le=10000)
    duration_seconds: int = Field(15, ge=1, le=86400)
    transition: str = Field(default="fade", max_length=48)
    repeat: bool = True

    @model_validator(mode="after")
    def source_valid(self):
        if self.item_type in {"image", "video", "pdf"} and not self.media_id:
            raise ValueError("Media item requires media_id")
        if self.widget_id and self.media_id:
            raise ValueError("Playlist item cannot reference both widget and media")
        return self


class ScheduleIn(BaseModel):
    playlist_id: int
    display_id: int | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    weekdays_json: list[int] = Field(default_factory=list)
    start_time: str = Field(default="00:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(default="23:59", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    priority: int = Field(default=100, ge=0, le=10000)
    is_active: bool = True

    @field_validator("weekdays_json")
    @classmethod
    def weekdays_valid(cls, values: list[int]) -> list[int]:
        if any(value < 0 or value > 6 for value in values):
            raise ValueError("Weekdays must use values 0 through 6")
        return sorted(set(values))

    @model_validator(mode="after")
    def dates_valid(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("Schedule end must be after its start")
        return self


class DisplaySettingsIn(BaseModel):
    refresh_interval_seconds: int = Field(ge=5, le=3600)
    default_transition: Literal["fade", "none", "slide"] = "fade"
    timezone: str = Field(min_length=2, max_length=80)
    offline_after_seconds: int = Field(ge=15, le=86400)
    weather_provider: str = Field(default="not_configured", max_length=80)
    theme: str = Field(default="organization", max_length=80)
    version: int = Field(ge=0)


class HeartbeatIn(BaseModel):
    browser: str = Field(default="", max_length=255)
    cpu_percent: float | None = Field(default=None, ge=0, le=100)
    ram_percent: float | None = Field(default=None, ge=0, le=100)
    connection: str = Field(default="", max_length=64)
    resolution: str = Field(default="", max_length=32)


class RuntimeHeartbeatIn(HeartbeatIn):
    displayCode: str
    playlist: str = ""
    uptime: int = Field(default=0, ge=0)
    fullscreen: bool = False


def _save(db: Session, entity, request: Request, user: User, action: str, details: dict | None = None):
    db.add(entity); db.flush()
    append_audit(db, actor=user.username, action=action, entity_type=entity.__tablename__, entity_id=entity.id, module="display_center", details=details or serialize(entity), **_audit_context(request))
    db.commit(); db.refresh(entity)
    return serialize(entity)


def _update(db: Session, model, entity_id: int, body: BaseModel, request: Request, user: User, action: str):
    entity = db.get(model, entity_id)
    if not entity: raise HTTPException(404, {"code": "not_found", "message": "Display Center record not found"})
    before = serialize(entity)
    for key, value in body.model_dump(exclude_unset=True).items(): setattr(entity, key, value)
    db.flush()
    append_audit(db, actor=user.username, action=action, entity_type=entity.__tablename__, entity_id=entity.id, module="display_center", details={"before": before, "after": serialize(entity)}, **_audit_context(request))
    db.commit(); db.refresh(entity)
    return serialize(entity)


def _remove(db: Session, entity, request: Request, user: User, action: str):
    append_audit(db, actor=user.username, action=action, entity_type=entity.__tablename__, entity_id=entity.id, module="display_center", details=serialize(entity), **_audit_context(request))
    db.delete(entity); db.commit()
    return {"status": "deleted"}


def _display_settings(db: Session) -> dict:
    return get_versioned_setting(db, "display_center.settings", DISPLAY_SETTINGS_DEFAULTS)


def _assert_playlist_refs(db: Session, body: PlaylistIn) -> None:
    if body.template_id and not db.get(DisplayTemplate, body.template_id):
        raise HTTPException(422, {"code": "template_not_found", "message": "Selected template does not exist"})


def _assert_display_refs(db: Session, body: DisplayIn) -> None:
    if body.playlist_id and not db.get(DisplayPlaylist, body.playlist_id):
        raise HTTPException(422, {"code": "playlist_not_found", "message": "Selected playlist does not exist"})


def _assert_schedule_refs(db: Session, body: ScheduleIn) -> None:
    if not db.get(DisplayPlaylist, body.playlist_id):
        raise HTTPException(422, {"code": "playlist_not_found", "message": "Selected playlist does not exist"})
    if body.display_id and not db.get(Display, body.display_id):
        raise HTTPException(422, {"code": "display_not_found", "message": "Selected display does not exist"})


def _assert_schedule_conflict(db: Session, body: ScheduleIn, exclude_id: int | None = None) -> None:
    if not body.is_active: return
    query = db.query(DisplaySchedule).filter(DisplaySchedule.is_active.is_(True), DisplaySchedule.display_id == body.display_id)
    if exclude_id is not None: query = query.filter(DisplaySchedule.id != exclude_id)
    def comparable(value: datetime | None) -> datetime | None:
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    for row in query.all():
        body_start, body_end = comparable(body.starts_at), comparable(body.ends_at)
        row_start, row_end = comparable(row.starts_at), comparable(row.ends_at)
        date_overlap = not (body_end and row_start and body_end <= row_start) and not (row_end and body_start and row_end <= body_start)
        days_overlap = not body.weekdays_json or not row.weekdays_json or bool(set(body.weekdays_json) & set(row.weekdays_json))
        time_overlap = not (body.end_time <= row.start_time or row.end_time <= body.start_time)
        if date_overlap and days_overlap and time_overlap and row.priority == body.priority:
            raise HTTPException(409, {"code": "schedule_overlap", "message": "An active schedule with the same priority overlaps this time window"})


def _assert_item_refs(db: Session, body: PlaylistItemIn) -> None:
    if body.widget_id and not db.get(DisplayWidget, body.widget_id): raise HTTPException(422, {"code": "widget_not_found", "message": "Selected widget does not exist"})
    if body.media_id and not db.get(DisplayMediaAsset, body.media_id): raise HTTPException(422, {"code": "media_not_found", "message": "Selected media does not exist"})


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))): return dashboard(db, _display_settings(db))


@router.get("/factory-dashboard")
def get_factory_dashboard(db: Session = Depends(get_db)): return factory_dashboard(db)


@router.get("/display/{display_code}")
def display_runtime(display_code: str, db: Session = Depends(get_db)):
    display = db.query(Display).filter(Display.code == display_code, Display.is_active.is_(True)).first()
    if not display: raise HTTPException(404, {"code": "display_not_found", "message": "Display code was not found or is inactive"})
    return runtime_payload(db, display, _display_settings(db))


@router.post("/heartbeat")
def runtime_heartbeat(body: RuntimeHeartbeatIn, db: Session = Depends(get_db)):
    display = db.query(Display).filter(Display.code == body.displayCode).first()
    if not display: raise HTTPException(404, {"code": "display_not_found", "message": "Display code not found"})
    return serialize(record_heartbeat(db, display, body.model_dump()))


@router.websocket("/ws/{display_code}")
async def display_ws(websocket: WebSocket, display_code: str):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text(); await websocket.send_json({"type": "keepalive", "displayCode": display_code})
    except WebSocketDisconnect:
        return


@router.get("/meta")
def meta(_: User = Depends(require_display("display_center_view"))): return {"widget_types": BUILT_IN_WIDGET_TYPES, "template_keys": TEMPLATE_KEYS, "realtime": {"transport": "websocket", "heartbeat_endpoint": "/display-center/heartbeat"}}


@router.get("/displays")
def displays(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))):
    offline_after = _display_settings(db)["offline_after_seconds"]; rows = []
    for entity in db.query(Display).order_by(Display.name).all():
        data = serialize(entity); data["effective_status"] = effective_display_status(entity, offline_after_seconds=offline_after); rows.append(data)
    return rows


@router.post("/displays")
def create_display(body: DisplayIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    _assert_display_refs(db, body)
    if db.query(Display).filter(Display.code == body.code).first(): raise HTTPException(409, {"code": "display_code_exists", "message": "Display code already exists"})
    return _save(db, Display(**body.model_dump()), request, user, "display.create")


@router.put("/displays/{entity_id}")
def edit_display(entity_id: int, body: DisplayIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    _assert_display_refs(db, body)
    if db.query(Display).filter(Display.code == body.code, Display.id != entity_id).first(): raise HTTPException(409, {"code": "display_code_exists", "message": "Display code already exists"})
    return _update(db, Display, entity_id, body, request, user, "display.update")


@router.delete("/displays/{entity_id}")
def delete_display(entity_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    entity = db.get(Display, entity_id)
    if not entity: raise HTTPException(404, "Display not found")
    if db.query(DisplaySchedule).filter(DisplaySchedule.display_id == entity_id).count(): raise HTTPException(409, {"code": "display_in_use", "message": "Remove display schedules before deleting the display"})
    return _remove(db, entity, request, user, "display.delete")


@router.post("/displays/{entity_id}/heartbeat")
def heartbeat(entity_id: int, body: HeartbeatIn, db: Session = Depends(get_db), _: User = Depends(require_display("display_center_manage"))):
    display = db.get(Display, entity_id)
    if not display: raise HTTPException(404, "Display not found")
    return serialize(record_heartbeat(db, display, body.model_dump()))


@router.get("/monitoring")
def monitoring(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))):
    offline_after = _display_settings(db)["offline_after_seconds"]; rows = []
    for display in db.query(Display).order_by(Display.name).all():
        latest = db.query(DisplayHeartbeat).filter(DisplayHeartbeat.display_id == display.id).order_by(DisplayHeartbeat.created_at.desc()).first()
        data = serialize(display); data["effective_status"] = effective_display_status(display, offline_after_seconds=offline_after); data["latest_heartbeat"] = serialize(latest) if latest else None; rows.append(data)
    return {"items": rows, "offline_after_seconds": offline_after}


@router.get("/widgets")
def widgets(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))): return [serialize(x) for x in db.query(DisplayWidget).order_by(DisplayWidget.name).all()]


@router.post("/widgets")
def create_widget(body: WidgetIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    if db.query(DisplayWidget).filter(DisplayWidget.key == body.key).first(): raise HTTPException(409, {"code": "widget_key_exists", "message": "Widget key already exists"})
    return _save(db, DisplayWidget(**body.model_dump()), request, user, "widget.create")


@router.put("/widgets/{entity_id}")
def edit_widget(entity_id: int, body: WidgetIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    if db.query(DisplayWidget).filter(DisplayWidget.key == body.key, DisplayWidget.id != entity_id).first(): raise HTTPException(409, {"code": "widget_key_exists", "message": "Widget key already exists"})
    return _update(db, DisplayWidget, entity_id, body, request, user, "widget.update")


@router.delete("/widgets/{entity_id}")
def delete_widget(entity_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    entity = db.get(DisplayWidget, entity_id)
    if not entity: raise HTTPException(404, "Widget not found")
    if db.query(DisplayPlaylistItem).filter(DisplayPlaylistItem.widget_id == entity_id).count(): raise HTTPException(409, {"code": "widget_in_use", "message": "Remove widget from playlists before deleting it"})
    return _remove(db, entity, request, user, "widget.delete")


@router.get("/playlists")
def playlists(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))): return [serialize(x) for x in db.query(DisplayPlaylist).order_by(DisplayPlaylist.name).all()]


@router.post("/playlists")
def create_playlist(body: PlaylistIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))): _assert_playlist_refs(db, body); return _save(db, DisplayPlaylist(**body.model_dump()), request, user, "playlist.create")


@router.put("/playlists/{entity_id}")
def edit_playlist(entity_id: int, body: PlaylistIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))): _assert_playlist_refs(db, body); return _update(db, DisplayPlaylist, entity_id, body, request, user, "playlist.update")


@router.delete("/playlists/{entity_id}")
def delete_playlist(entity_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    entity = db.get(DisplayPlaylist, entity_id)
    if not entity: raise HTTPException(404, "Playlist not found")
    if db.query(Display).filter(Display.playlist_id == entity_id).count() or db.query(DisplaySchedule).filter(DisplaySchedule.playlist_id == entity_id).count(): raise HTTPException(409, {"code": "playlist_in_use", "message": "Unassign the playlist from displays and schedules before deleting it"})
    return _remove(db, entity, request, user, "playlist.delete")


@router.get("/templates")
def templates(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))): return [serialize(x) for x in db.query(DisplayTemplate).order_by(DisplayTemplate.name).all()]


@router.post("/templates")
def create_template(body: TemplateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))): return _save(db, DisplayTemplate(**body.model_dump()), request, user, "template.create")


@router.get("/templates/{entity_id}")
def get_template(entity_id: int, db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))):
    entity = db.get(DisplayTemplate, entity_id)
    if not entity: raise HTTPException(404, "Template not found")
    return serialize(entity)


@router.put("/templates/{entity_id}")
def save_template(entity_id: int, body: TemplateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))): return _update(db, DisplayTemplate, entity_id, body, request, user, "template.update")


@router.post("/templates/{entity_id}/clone")
def clone_template(entity_id: int, body: TemplateCloneIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    source = db.get(DisplayTemplate, entity_id)
    if not source: raise HTTPException(404, "Template not found")
    clone = DisplayTemplate(name=(body.name or f"{source.name} copy").strip(), category=source.category, canvas_json=source.canvas_json, layout_json=source.layout_json, is_active=source.is_active)
    return _save(db, clone, request, user, "template.clone", {"source_id": source.id, "name": clone.name})


@router.delete("/templates/{entity_id}")
def delete_template(entity_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    entity = db.get(DisplayTemplate, entity_id)
    if not entity: raise HTTPException(404, "Template not found")
    if db.query(DisplayPlaylist).filter(DisplayPlaylist.template_id == entity_id).count(): raise HTTPException(409, {"code": "template_in_use", "message": "Unassign the template from playlists before deleting it"})
    return _remove(db, entity, request, user, "template.delete")


@router.get("/playlists/{playlist_id}/items")
def playlist_items(playlist_id: int, db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))):
    if not db.get(DisplayPlaylist, playlist_id): raise HTTPException(404, "Playlist not found")
    return [serialize(x) for x in db.query(DisplayPlaylistItem).filter_by(playlist_id=playlist_id).order_by(DisplayPlaylistItem.position).all()]


@router.post("/playlists/{playlist_id}/items")
def add_item(playlist_id: int, body: PlaylistItemIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    if not db.get(DisplayPlaylist, playlist_id): raise HTTPException(404, "Playlist not found")
    _assert_item_refs(db, body); return _save(db, DisplayPlaylistItem(playlist_id=playlist_id, **body.model_dump()), request, user, "playlist_item.create")


@router.put("/playlist-items/{entity_id}")
def edit_item(entity_id: int, body: PlaylistItemIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))): _assert_item_refs(db, body); return _update(db, DisplayPlaylistItem, entity_id, body, request, user, "playlist_item.update")


@router.delete("/playlist-items/{entity_id}")
def delete_item(entity_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    entity = db.get(DisplayPlaylistItem, entity_id)
    if not entity: raise HTTPException(404, "Playlist item not found")
    return _remove(db, entity, request, user, "playlist_item.delete")


@router.get("/schedules")
def schedules(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))): return [serialize(x) for x in db.query(DisplaySchedule).order_by(DisplaySchedule.priority.asc(), DisplaySchedule.id.asc()).all()]


@router.post("/schedules")
def create_schedule(body: ScheduleIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))): _assert_schedule_refs(db, body); _assert_schedule_conflict(db, body); return _save(db, DisplaySchedule(**body.model_dump()), request, user, "schedule.create")


@router.put("/schedules/{entity_id}")
def edit_schedule(entity_id: int, body: ScheduleIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))): _assert_schedule_refs(db, body); _assert_schedule_conflict(db, body, entity_id); return _update(db, DisplaySchedule, entity_id, body, request, user, "schedule.update")


@router.delete("/schedules/{entity_id}")
def delete_schedule(entity_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    entity = db.get(DisplaySchedule, entity_id)
    if not entity: raise HTTPException(404, "Schedule not found")
    return _remove(db, entity, request, user, "schedule.delete")


@router.get("/media")
def media(q: str = "", db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))):
    query = db.query(DisplayMediaAsset)
    if q: query = query.filter(DisplayMediaAsset.name.ilike(f"%{q}%"))
    return [serialize(x) for x in query.order_by(DisplayMediaAsset.created_at.desc()).all()]


def _valid_media_signature(content_type: str, content: bytes) -> bool:
    return {"image/png": content.startswith(b"\x89PNG\r\n\x1a\n"), "image/jpeg": content.startswith(b"\xff\xd8\xff"), "image/webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP", "application/pdf": content.startswith(b"%PDF-"), "video/mp4": len(content) > 12 and content[4:8] == b"ftyp", "video/webm": content.startswith(b"\x1aE\xdf\xa3")}.get(content_type, False)


@router.post("/media/upload")
async def upload_media(request: Request, file: UploadFile = File(...), folder_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    content_type = (file.content_type or "").lower(); content = await file.read(MAX_MEDIA_BYTES + 1)
    if len(content) > MAX_MEDIA_BYTES: raise HTTPException(413, {"code": "media_too_large", "message": "Media file exceeds the 25 MB limit"})
    if not _valid_media_signature(content_type, content): raise HTTPException(415, {"code": "unsupported_media", "message": "Upload a valid PNG, JPEG, WebP, PDF, MP4, or WebM file"})
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "application/pdf": ".pdf", "video/mp4": ".mp4", "video/webm": ".webm"}[content_type]
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True); stored = f"{uuid4().hex}{suffix}"; target = MEDIA_ROOT / stored; target.write_bytes(content)
    media_type = "image" if content_type.startswith("image/") else "video" if content_type.startswith("video/") else "pdf"
    asset = DisplayMediaAsset(folder_id=folder_id, name=Path(file.filename or stored).stem[:255], original_filename=Path(file.filename or stored).name[:255], media_type=media_type, content_type=content_type, path=f"/uploads/display-center/{stored}", size_bytes=len(content))
    try: return _save(db, asset, request, user, "media.upload", {"name": asset.name, "content_type": content_type, "size_bytes": len(content)})
    except Exception:
        target.unlink(missing_ok=True); raise


@router.delete("/media/{entity_id}")
def delete_media(entity_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    entity = db.get(DisplayMediaAsset, entity_id)
    if not entity: raise HTTPException(404, "Media not found")
    if db.query(DisplayPlaylistItem).filter(DisplayPlaylistItem.media_id == entity_id).count(): raise HTTPException(409, {"code": "media_in_use", "message": "Remove media from playlists before deleting it"})
    filename = Path(entity.path).name; result = _remove(db, entity, request, user, "media.delete"); target = (MEDIA_ROOT / filename).resolve()
    if target.parent == MEDIA_ROOT.resolve(): target.unlink(missing_ok=True)
    return result


@router.get("/settings")
def display_settings(db: Session = Depends(get_db), _: User = Depends(require_display("display_center_view"))): return _display_settings(db)


@router.put("/settings")
def save_display_settings(body: DisplaySettingsIn, request: Request, db: Session = Depends(get_db), user: User = Depends(require_display("display_center_manage"))):
    try: result = put_versioned_setting(db, "display_center.settings", body.model_dump(exclude={"version"}), body.version)
    except ValueError as exc: raise HTTPException(409, {"code": "version_conflict", "message": str(exc)}) from exc
    append_audit(db, actor=user.username, action="display_settings.update", entity_type="display_center_settings", module="display_center", details=body.model_dump(exclude={"version"}), **_audit_context(request)); db.commit(); return result
