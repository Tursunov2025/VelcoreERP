from __future__ import annotations

from datetime import datetime, timezone, timedelta

from models import MesGpsCommandQueue, MesGpsDevice


MAX_SIGNAL_AGE_SECONDS = 90.0


def evaluate_pending_command(db, device_identifier: str, zero_speed_streak: int = 0) -> dict:
    device = (
        db.query(MesGpsDevice)
        .filter(MesGpsDevice.device_identifier == device_identifier)
        .first()
    )

    if not device:
        return {"eligible": False, "reason": "device_not_found"}

    command = (
        db.query(MesGpsCommandQueue)
        .filter(
            MesGpsCommandQueue.device_id == device.id,
            MesGpsCommandQueue.status.in_(["pending", "armed"]),
        )
        .order_by(MesGpsCommandQueue.id.asc())
        .first()
    )

    if not command:
        return {"eligible": False, "reason": "no_pending_command"}

    speed = float(device.last_speed_kmh or 0.0)

    last_seen = device.last_seen_at
    if last_seen is None:
        return {
            "eligible": False,
            "reason": "no_recent_signal",
            "command_id": command.id,
        }

    now = datetime.now(timezone.utc)
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    age_seconds = (now - last_seen).total_seconds()

    if age_seconds > MAX_SIGNAL_AGE_SECONDS:
        return {
            "eligible": False,
            "reason": "stale_signal",
            "command_id": command.id,
            "signal_age_seconds": round(age_seconds, 1),
        }

    if command.action == "BLOCK" and speed > 0.0:
        return {
            "eligible": False,
            "reason": "vehicle_moving",
            "command_id": command.id,
            "speed_kmh": speed,
        }

    if command.action == "BLOCK" and zero_speed_streak < 3:
        return {
            "eligible": False,
            "reason": "stop_not_confirmed",
            "command_id": command.id,
            "speed_kmh": speed,
            "zero_speed_streak": zero_speed_streak,
        }

    return {
        "eligible": True,
        "dry_run": True,
        "command_id": command.id,
        "action": command.action,
        "status": command.status,
        "device_identifier": device_identifier,
        "speed_kmh": speed,
        "signal_age_seconds": round(age_seconds, 1),
        "zero_speed_streak": zero_speed_streak,
    }


def mark_command_ready(db, command_id: int) -> dict:
    command = (
        db.query(MesGpsCommandQueue)
        .filter(MesGpsCommandQueue.id == command_id)
        .first()
    )

    if not command:
        return {"updated": False, "reason": "command_not_found"}

    if command.status == "ready":
        return {
            "updated": False,
            "reason": "already_ready",
            "command_id": command.id,
        }

    if command.status not in {"pending", "armed"}:
        return {
            "updated": False,
            "reason": "invalid_status",
            "command_id": command.id,
            "status": command.status,
        }

    command.status = "ready"
    db.commit()
    db.refresh(command)

    return {
        "updated": True,
        "command_id": command.id,
        "action": command.action,
        "status": command.status,
    }


def mark_command_sent(db, command_id: int) -> dict:
    now = datetime.utcnow()

    updated = (
        db.query(MesGpsCommandQueue)
        .filter(
            MesGpsCommandQueue.id == command_id,
            MesGpsCommandQueue.status == "ready",
        )
        .update(
            {
                MesGpsCommandQueue.status: "sent",
                MesGpsCommandQueue.sent_at: now,
            },
            synchronize_session=False,
        )
    )

    if updated != 1:
        db.rollback()
        command = (
            db.query(MesGpsCommandQueue)
            .filter(MesGpsCommandQueue.id == command_id)
            .first()
        )
        if not command:
            return {"updated": False, "reason": "command_not_found"}

        return {
            "updated": False,
            "reason": "already_claimed",
            "command_id": command.id,
            "status": command.status,
        }

    db.commit()

    command = (
        db.query(MesGpsCommandQueue)
        .filter(MesGpsCommandQueue.id == command_id)
        .first()
    )

    return {
        "updated": True,
        "command_id": command.id,
        "action": command.action,
        "status": command.status,
        "sent_at": command.sent_at,
    }

def mark_command_acked(db, command_id: int) -> dict:
    command = (
        db.query(MesGpsCommandQueue)
        .filter(MesGpsCommandQueue.id == command_id)
        .first()
    )

    if not command:
        return {"updated": False, "reason": "command_not_found"}

    if command.status == "acked":
        return {
            "updated": False,
            "reason": "already_acked",
            "command_id": command.id,
        }

    if command.status != "sent":
        return {
            "updated": False,
            "reason": "invalid_status",
            "command_id": command.id,
            "status": command.status,
        }

    command.status = "acked"
    command.acked_at = datetime.utcnow()
    db.commit()
    db.refresh(command)

    return {
        "updated": True,
        "command_id": command.id,
        "action": command.action,
        "status": command.status,
        "acked_at": command.acked_at,
    }



def ack_latest_sent_command(db, device_identifier: str, max_age_seconds: int = 120) -> dict:
    device = (
        db.query(MesGpsDevice)
        .filter(MesGpsDevice.device_identifier == device_identifier)
        .first()
    )

    if not device:
        return {"updated": False, "reason": "device_not_found"}

    cutoff = datetime.utcnow() - timedelta(seconds=max_age_seconds)

    command = (
        db.query(MesGpsCommandQueue)
        .filter(
            MesGpsCommandQueue.device_id == device.id,
            MesGpsCommandQueue.status == "sent",
            MesGpsCommandQueue.sent_at.isnot(None),
            MesGpsCommandQueue.sent_at >= cutoff,
        )
        .order_by(MesGpsCommandQueue.sent_at.desc())
        .first()
    )

    if not command:
        return {"updated": False, "reason": "recent_sent_command_not_found"}

    return mark_command_acked(db, command.id)


def build_s20_command(device_identifier: str, action: str, hhmmss: str) -> bytes:
    action = str(action).upper().strip()

    if action == "BLOCK":
        relay_value = "1"
    elif action == "UNBLOCK":
        relay_value = "0"
    else:
        raise ValueError("action must be BLOCK or UNBLOCK")

    if not device_identifier.isdigit():
        raise ValueError("invalid device identifier")

    if len(hhmmss) != 6 or not hhmmss.isdigit():
        raise ValueError("hhmmss must contain exactly 6 digits")

    return f"*HQ,{device_identifier},S20,{hhmmss},1,{relay_value}#".encode("ascii")


def get_ready_command(db, device_identifier: str) -> dict:
    device = (
        db.query(MesGpsDevice)
        .filter(MesGpsDevice.device_identifier == device_identifier)
        .first()
    )

    if not device:
        return {"found": False, "reason": "device_not_found"}

    command = (
        db.query(MesGpsCommandQueue)
        .filter(
            MesGpsCommandQueue.device_id == device.id,
            MesGpsCommandQueue.status == "ready",
        )
        .order_by(MesGpsCommandQueue.id.asc())
        .first()
    )

    if not command:
        return {"found": False, "reason": "no_ready_command"}

    return {
        "found": True,
        "command_id": command.id,
        "action": command.action,
        "status": command.status,
        "device_identifier": device.device_identifier,
    }
