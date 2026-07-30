from __future__ import annotations
from datetime import datetime
from models import Display, DisplayHeartbeat, DisplayPlaylist

BUILT_IN_WIDGET_TYPES = ["clock", "date", "weather", "orders", "production", "warehouse", "kpi", "news", "video", "image", "html", "pdf", "safety_message", "birthday", "employee_of_month", "qr_code", "announcement"]
TEMPLATE_KEYS = ["factory_dashboard", "warehouse_dashboard", "office_dashboard", "reception_dashboard", "advertising", "kpi"]

def serialize(model):
    data = {c.name: getattr(model, c.name) for c in model.__table__.columns}
    for key, value in data.items():
        if isinstance(value, datetime): data[key] = value.isoformat()
    return data

def dashboard(db):
    from models import DisplayMediaAsset, DisplayWidget
    displays = db.query(Display).all()
    return {"online_displays": sum(d.status == "online" for d in displays), "offline_displays": sum(d.status != "online" for d in displays), "active_playlists": db.query(DisplayPlaylist).filter_by(is_active=True).count(), "images": db.query(DisplayMediaAsset).filter_by(media_type="image").count(), "videos": db.query(DisplayMediaAsset).filter_by(media_type="video").count(), "widgets": db.query(DisplayWidget).filter_by(is_active=True).count(), "recent_activity": [serialize(h) for h in db.query(DisplayHeartbeat).order_by(DisplayHeartbeat.created_at.desc()).limit(10)]}

def record_heartbeat(db, display, payload):
    display.last_seen = datetime.utcnow(); display.status = "online"
    heartbeat = DisplayHeartbeat(display_id=display.id, browser=payload.get("browser", ""), cpu_percent=payload.get("cpu_percent"), ram_percent=payload.get("ram_percent"), connection=payload.get("connection", ""), resolution=payload.get("resolution", ""), payload_json=payload)
    db.add(heartbeat); db.commit(); db.refresh(heartbeat); return heartbeat

def runtime_payload(db, display):
    """Device-safe contract: only the selected playlist and referenced assets/widgets."""
    from models import DisplayMediaAsset, DisplayPlaylistItem, DisplayWidget
    playlist = db.get(DisplayPlaylist, display.playlist_id) if display.playlist_id else None
    items = []
    if playlist:
        for item in db.query(DisplayPlaylistItem).filter_by(playlist_id=playlist.id).order_by(DisplayPlaylistItem.position):
            data = serialize(item)
            data["widget"] = serialize(db.get(DisplayWidget, item.widget_id)) if item.widget_id else None
            data["media"] = serialize(db.get(DisplayMediaAsset, item.media_id)) if item.media_id else None
            items.append(data)
    return {"display": serialize(display), "playlist": serialize(playlist) if playlist else None, "items": items, "widgets": [x["widget"] for x in items if x.get("widget")], "settings": {"refresh_interval_seconds": 30, "default_transition": "fade", "timezone": "Asia/Tashkent", "orientation": display.orientation}}
