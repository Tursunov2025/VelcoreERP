"""Versioned, extensible Digital Signage API. WebSocket delivery can subscribe to heartbeat events later."""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from auth.deps import get_current_user
from database import get_db
from models import Display, DisplayMediaAsset, DisplayMediaFolder, DisplayPlaylist, DisplayPlaylistItem, DisplaySchedule, DisplayWidget, User
from repositories.display_center_repository import DisplayCenterRepository
from services.display_center import BUILT_IN_WIDGET_TYPES, TEMPLATE_KEYS, dashboard, record_heartbeat, serialize

router = APIRouter(prefix="/display-center", tags=["display-center"])
MEDIA_ROOT = Path(__file__).resolve().parents[1] / "uploads" / "display-center"

def admin(user: User = Depends(get_current_user)):
    if user.role != "admin": raise HTTPException(403, "Display Center requires administrator access")
    return user

class DisplayIn(BaseModel):
    name: str; code: str; location: str = ""; description: str = ""; ip_address: str = ""; resolution: str = "1920x1080"; orientation: str = "landscape"; playlist_id: int | None = None
class WidgetIn(BaseModel):
    key: str; name: str; widget_type: str; settings_json: dict = Field(default_factory=dict); is_active: bool = True
class PlaylistIn(BaseModel):
    name: str; description: str = ""; template_key: str = "custom"; is_active: bool = True
class PlaylistItemIn(BaseModel):
    item_type: str; widget_id: int | None = None; media_id: int | None = None; settings_json: dict = Field(default_factory=dict); position: int = 0; duration_seconds: int = Field(15, ge=1); transition: str = "fade"; repeat: bool = True
class ScheduleIn(BaseModel):
    playlist_id: int; display_id: int | None = None; starts_at: datetime | None = None; ends_at: datetime | None = None; weekdays_json: list[int] = Field(default_factory=list); start_time: str = "00:00"; end_time: str = "23:59"; priority: int = 100; is_active: bool = True
class HeartbeatIn(BaseModel):
    browser: str = ""; cpu_percent: float | None = None; ram_percent: float | None = None; connection: str = ""; resolution: str = ""

def crud(model, body, db):
    entity = model(**body.model_dump()); return serialize(DisplayCenterRepository(db).save(entity))
def update(model, entity_id, body, db):
    entity = DisplayCenterRepository(db).get(model, entity_id)
    if not entity: raise HTTPException(404, "Not found")
    for key, value in body.model_dump(exclude_unset=True).items(): setattr(entity, key, value)
    return serialize(DisplayCenterRepository(db).save(entity))
def remove(model, entity_id, db):
    entity = DisplayCenterRepository(db).get(model, entity_id)
    if not entity: raise HTTPException(404, "Not found")
    DisplayCenterRepository(db).delete(entity); return {"ok": True}

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(admin)): return dashboard(db)
@router.get("/meta")
def meta(_: User = Depends(admin)): return {"widget_types": BUILT_IN_WIDGET_TYPES, "template_keys": TEMPLATE_KEYS, "realtime": {"transport": "websocket-ready", "heartbeat_endpoint": "/display-center/displays/{id}/heartbeat"}}
@router.get("/displays")
def displays(db: Session = Depends(get_db), _: User = Depends(admin)): return [serialize(x) for x in DisplayCenterRepository(db).list(Display, Display.name)]
@router.post("/displays")
def create_display(body: DisplayIn, db: Session = Depends(get_db), _: User = Depends(admin)): return crud(Display, body, db)
@router.put("/displays/{entity_id}")
def edit_display(entity_id: int, body: DisplayIn, db: Session = Depends(get_db), _: User = Depends(admin)): return update(Display, entity_id, body, db)
@router.delete("/displays/{entity_id}")
def delete_display(entity_id: int, db: Session = Depends(get_db), _: User = Depends(admin)): return remove(Display, entity_id, db)
@router.post("/displays/{entity_id}/heartbeat")
def heartbeat(entity_id: int, body: HeartbeatIn, db: Session = Depends(get_db)):
    display = db.get(Display, entity_id)
    if not display: raise HTTPException(404, "Display not found")
    return serialize(record_heartbeat(db, display, body.model_dump()))
@router.get("/widgets")
def widgets(db: Session = Depends(get_db), _: User = Depends(admin)): return [serialize(x) for x in DisplayCenterRepository(db).list(DisplayWidget, DisplayWidget.name)]
@router.post("/widgets")
def create_widget(body: WidgetIn, db: Session = Depends(get_db), _: User = Depends(admin)): return crud(DisplayWidget, body, db)
@router.put("/widgets/{entity_id}")
def edit_widget(entity_id: int, body: WidgetIn, db: Session = Depends(get_db), _: User = Depends(admin)): return update(DisplayWidget, entity_id, body, db)
@router.delete("/widgets/{entity_id}")
def delete_widget(entity_id: int, db: Session = Depends(get_db), _: User = Depends(admin)): return remove(DisplayWidget, entity_id, db)
@router.get("/playlists")
def playlists(db: Session = Depends(get_db), _: User = Depends(admin)): return [serialize(x) for x in DisplayCenterRepository(db).list(DisplayPlaylist, DisplayPlaylist.name)]
@router.post("/playlists")
def create_playlist(body: PlaylistIn, db: Session = Depends(get_db), _: User = Depends(admin)): return crud(DisplayPlaylist, body, db)
@router.put("/playlists/{entity_id}")
def edit_playlist(entity_id: int, body: PlaylistIn, db: Session = Depends(get_db), _: User = Depends(admin)): return update(DisplayPlaylist, entity_id, body, db)
@router.delete("/playlists/{entity_id}")
def delete_playlist(entity_id: int, db: Session = Depends(get_db), _: User = Depends(admin)): return remove(DisplayPlaylist, entity_id, db)
@router.get("/playlists/{playlist_id}/items")
def playlist_items(playlist_id: int, db: Session = Depends(get_db), _: User = Depends(admin)): return [serialize(x) for x in db.query(DisplayPlaylistItem).filter_by(playlist_id=playlist_id).order_by(DisplayPlaylistItem.position)]
@router.post("/playlists/{playlist_id}/items")
def add_item(playlist_id: int, body: PlaylistItemIn, db: Session = Depends(get_db), _: User = Depends(admin)): return serialize(DisplayCenterRepository(db).save(DisplayPlaylistItem(playlist_id=playlist_id, **body.model_dump())))
@router.put("/playlist-items/{entity_id}")
def edit_item(entity_id: int, body: PlaylistItemIn, db: Session = Depends(get_db), _: User = Depends(admin)): return update(DisplayPlaylistItem, entity_id, body, db)
@router.delete("/playlist-items/{entity_id}")
def delete_item(entity_id: int, db: Session = Depends(get_db), _: User = Depends(admin)): return remove(DisplayPlaylistItem, entity_id, db)
@router.get("/schedules")
def schedules(db: Session = Depends(get_db), _: User = Depends(admin)): return [serialize(x) for x in DisplayCenterRepository(db).list(DisplaySchedule, DisplaySchedule.priority.desc())]
@router.post("/schedules")
def create_schedule(body: ScheduleIn, db: Session = Depends(get_db), _: User = Depends(admin)): return crud(DisplaySchedule, body, db)
@router.delete("/schedules/{entity_id}")
def delete_schedule(entity_id: int, db: Session = Depends(get_db), _: User = Depends(admin)): return remove(DisplaySchedule, entity_id, db)
@router.get("/media")
def media(q: str = "", db: Session = Depends(get_db), _: User = Depends(admin)):
    query = db.query(DisplayMediaAsset)
    if q: query = query.filter(DisplayMediaAsset.name.ilike(f"%{q}%"))
    return [serialize(x) for x in query.order_by(DisplayMediaAsset.created_at.desc()).all()]
@router.post("/media/upload")
async def upload_media(file: UploadFile = File(...), folder_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(admin)):
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True); suffix = Path(file.filename or "asset").suffix.lower(); media_type = "image" if file.content_type and file.content_type.startswith("image/") else "video" if file.content_type and file.content_type.startswith("video/") else "document"
    stored = f"{uuid4().hex}{suffix}"; target = MEDIA_ROOT / stored; content = await file.read(); target.write_bytes(content)
    asset = DisplayMediaAsset(folder_id=folder_id, name=Path(file.filename or stored).stem, original_filename=file.filename or stored, media_type=media_type, content_type=file.content_type or "", path=f"/uploads/display-center/{stored}", size_bytes=len(content))
    return serialize(DisplayCenterRepository(db).save(asset))
@router.delete("/media/{entity_id}")
def delete_media(entity_id: int, db: Session = Depends(get_db), _: User = Depends(admin)): return remove(DisplayMediaAsset, entity_id, db)
