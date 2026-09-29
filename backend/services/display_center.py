from __future__ import annotations
from datetime import datetime, timedelta, timezone
from models import Display, DisplayHeartbeat, DisplayPlaylist, DisplaySchedule, DisplayTemplate

BUILT_IN_WIDGET_TYPES = ["clock", "date", "weather", "orders", "production", "warehouse", "kpi", "news", "video", "image", "html", "pdf", "safety_message", "birthday", "employee_of_month", "qr_code", "announcement"]
TEMPLATE_KEYS = ["factory_dashboard", "warehouse_dashboard", "office_dashboard", "reception_dashboard", "advertising", "kpi"]

def serialize(model):
    data = {c.name: getattr(model, c.name) for c in model.__table__.columns}
    for key, value in data.items():
        if isinstance(value, datetime): data[key] = value.isoformat()
    return data

DISPLAY_SETTINGS_DEFAULTS = {
    "refresh_interval_seconds": 30,
    "default_transition": "fade",
    "timezone": "Asia/Tashkent",
    "offline_after_seconds": 90,
    "weather_provider": "not_configured",
    "theme": "organization",
}


def effective_display_status(display, *, now: datetime | None = None, offline_after_seconds: int = 90) -> str:
    now = now or datetime.utcnow()
    if not getattr(display, "is_active", True):
        return "inactive"
    if not display.last_seen or display.last_seen < now - timedelta(seconds=offline_after_seconds):
        return "offline"
    return "online"


def dashboard(db, settings=None):
    from models import DisplayMediaAsset, DisplayWidget
    displays = db.query(Display).all()
    offline_after = int((settings or {}).get("offline_after_seconds", 90))
    statuses = [effective_display_status(d, offline_after_seconds=offline_after) for d in displays]
    return {"online_displays": statuses.count("online"), "offline_displays": statuses.count("offline"), "inactive_displays": statuses.count("inactive"), "active_playlists": db.query(DisplayPlaylist).filter_by(is_active=True).count(), "active_schedules": db.query(DisplaySchedule).filter_by(is_active=True).count(), "images": db.query(DisplayMediaAsset).filter_by(media_type="image").count(), "videos": db.query(DisplayMediaAsset).filter_by(media_type="video").count(), "widgets": db.query(DisplayWidget).filter_by(is_active=True).count(), "recent_activity": [serialize(h) for h in db.query(DisplayHeartbeat).order_by(DisplayHeartbeat.created_at.desc()).limit(10)]}

def record_heartbeat(db, display, payload):
    display.last_seen = datetime.utcnow(); display.status = "online" if getattr(display, "is_active", True) else "inactive"
    heartbeat = DisplayHeartbeat(display_id=display.id, browser=payload.get("browser", ""), cpu_percent=payload.get("cpu_percent"), ram_percent=payload.get("ram_percent"), connection=payload.get("connection", ""), resolution=payload.get("resolution", ""), payload_json=payload)
    db.add(heartbeat); db.commit(); db.refresh(heartbeat); return heartbeat

def _schedule_matches(schedule: DisplaySchedule, now: datetime) -> bool:
    if not schedule.is_active:
        return False
    if now.tzinfo is not None:
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    starts_at = schedule.starts_at.astimezone(timezone.utc).replace(tzinfo=None) if schedule.starts_at and schedule.starts_at.tzinfo else schedule.starts_at
    ends_at = schedule.ends_at.astimezone(timezone.utc).replace(tzinfo=None) if schedule.ends_at and schedule.ends_at.tzinfo else schedule.ends_at
    if starts_at and now < starts_at:
        return False
    if ends_at and now > ends_at:
        return False
    weekdays = schedule.weekdays_json or []
    if weekdays and now.weekday() not in weekdays:
        return False
    current = now.strftime("%H:%M")
    start = (schedule.start_time or "00:00")[:5]
    end = (schedule.end_time or "23:59")[:5]
    return start <= current <= end if start <= end else current >= start or current <= end


def resolve_runtime_playlist(db, display, now: datetime | None = None):
    now = now or datetime.utcnow()
    schedules = (
        db.query(DisplaySchedule)
        .filter(DisplaySchedule.is_active.is_(True))
        .order_by(DisplaySchedule.priority.asc(), DisplaySchedule.id.asc())
        .all()
    )
    selected = next(
        (row for row in schedules if row.display_id in (None, display.id) and _schedule_matches(row, now)),
        None,
    )
    playlist_id = selected.playlist_id if selected else display.playlist_id
    playlist = db.get(DisplayPlaylist, playlist_id) if playlist_id else None
    if playlist and not playlist.is_active:
        playlist = None
    return playlist, selected


def runtime_payload(db, display, settings=None, now: datetime | None = None):
    """Device-safe contract: only the selected playlist and referenced assets/widgets."""
    from models import DisplayMediaAsset, DisplayPlaylistItem, DisplayWidget
    playlist, schedule = resolve_runtime_playlist(db, display, now)
    template = db.get(DisplayTemplate, playlist.template_id) if playlist and playlist.template_id else None
    items = []
    if playlist:
        for item in db.query(DisplayPlaylistItem).filter_by(playlist_id=playlist.id).order_by(DisplayPlaylistItem.position):
            data = serialize(item)
            data["widget"] = serialize(db.get(DisplayWidget, item.widget_id)) if item.widget_id else None
            data["media"] = serialize(db.get(DisplayMediaAsset, item.media_id)) if item.media_id else None
            items.append(data)
    if template and not items:
        for index, widget in enumerate((template.layout_json or {}).get("widgets", [])):
            items.append({
                "id": f"template-{template.id}-{widget.get('id', index)}",
                "item_type": widget.get("type", "text"),
                "position": index,
                "duration_seconds": int(widget.get("duration", 15) or 15),
                "transition": widget.get("transition", "fade"),
                "settings_json": widget,
                "widget": None,
                "media": None,
            })
    runtime_settings = {**DISPLAY_SETTINGS_DEFAULTS, **(settings or {}), "orientation": display.orientation}
    return {"display": serialize(display), "playlist": serialize(playlist) if playlist else None, "schedule": serialize(schedule) if schedule else None, "template": serialize(template) if template else None, "items": items, "widgets": [x["widget"] for x in items if x.get("widget")], "settings": runtime_settings}
