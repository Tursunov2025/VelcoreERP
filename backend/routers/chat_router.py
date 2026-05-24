from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import ChatMessage, ChatNotification, ChatReadState, ChatRoom, User
from services.activity import get_online_operators_detailed

router = APIRouter(prefix="/chat", tags=["chat"])

_typing_state: dict[str, dict] = {}
TYPING_TTL_SECONDS = 8


class SendMessageRequest(BaseModel):
    content: str = ""
    message_type: str = "text"
    attachment_url: Optional[str] = None


class PrivateRoomRequest(BaseModel):
    username: str


class TypingRequest(BaseModel):
    room_id: int
    is_typing: bool = True


def _is_admin(user: User) -> bool:
    return user.role == "admin" or user.department == "Admin"


def _can_access_room(user: User, room: ChatRoom) -> bool:
    if _is_admin(user):
        return True
    if room.room_type == "announcement":
        return True
    if room.room_type == "department":
        return user.department == room.department or user.department == "Admin"
    if room.room_type == "private":
        return user.username in (room.participant_a, room.participant_b)
    return False


def _serialize_message(msg: ChatMessage) -> dict:
    return {
        "id": msg.id,
        "room_id": msg.room_id,
        "sender_username": msg.sender_username,
        "sender_department": msg.sender_department,
        "content": msg.content,
        "message_type": msg.message_type,
        "attachment_url": msg.attachment_url,
        "created_at": msg.created_at,
    }


def _unread_count(db: Session, username: str, room_id: int) -> int:
    state = (
        db.query(ChatReadState)
        .filter(ChatReadState.username == username, ChatReadState.room_id == room_id)
        .first()
    )
    last_id = state.last_read_message_id if state else 0
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.room_id == room_id, ChatMessage.id > last_id)
        .count()
    )


@router.get("/rooms")
def list_rooms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rooms = db.query(ChatRoom).order_by(ChatRoom.id).all()
    accessible = [r for r in rooms if _can_access_room(user, r)]

    result = []
    for room in accessible:
        last_msg = (
            db.query(ChatMessage)
            .filter(ChatMessage.room_id == room.id)
            .order_by(ChatMessage.id.desc())
            .first()
        )
        result.append(
            {
                "id": room.id,
                "name": room.name,
                "room_type": room.room_type,
                "department": room.department,
                "participant_a": room.participant_a,
                "participant_b": room.participant_b,
                "last_message": _serialize_message(last_msg) if last_msg else None,
                "unread_count": _unread_count(db, user.username, room.id),
            }
        )

    result.sort(key=lambda r: (r["unread_count"] == 0, -(r["last_message"]["id"] if r["last_message"] else 0)))
    return {"rooms": result}


@router.get("/rooms/{room_id}/messages")
def get_messages(
    room_id: int,
    since_id: int = Query(0),
    limit: int = Query(80, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not _can_access_room(user, room):
        raise HTTPException(status_code=403, detail="Access denied")

    query = db.query(ChatMessage).filter(ChatMessage.room_id == room_id)
    if since_id:
        query = query.filter(ChatMessage.id > since_id)
    else:
        query = query.order_by(ChatMessage.id.desc()).limit(limit)
        msgs = list(reversed(query.all()))
        return {"messages": [_serialize_message(m) for m in msgs]}

    msgs = query.order_by(ChatMessage.id.asc()).limit(limit).all()
    return {"messages": [_serialize_message(m) for m in msgs]}


@router.post("/rooms/{room_id}/messages")
def send_message(
    room_id: int,
    data: SendMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not _can_access_room(user, room):
        raise HTTPException(status_code=403, detail="Access denied")

    if room.room_type == "announcement" and not _is_admin(user):
        raise HTTPException(status_code=403, detail="Only admin can post announcements")

    content = (data.content or "").strip()
    if not content and not data.attachment_url:
        raise HTTPException(status_code=400, detail="Empty message")

    msg = ChatMessage(
        room_id=room_id,
        sender_username=user.username,
        sender_department=user.department or user.role,
        content=content,
        message_type=data.message_type or "text",
        attachment_url=data.attachment_url,
    )
    db.add(msg)
    db.flush()

    participants = set()
    if room.room_type == "private":
        participants.update([room.participant_a, room.participant_b])
    else:
        users = db.query(User).filter(User.is_active.isnot(False)).all()
        for u in users:
            if _can_access_room(u, room) and u.username != user.username:
                participants.add(u.username)

    for username in participants:
        db.add(
            ChatNotification(
                username=username,
                room_id=room_id,
                message_id=msg.id,
            )
        )

    state = (
        db.query(ChatReadState)
        .filter(ChatReadState.username == user.username, ChatReadState.room_id == room_id)
        .first()
    )
    if not state:
        state = ChatReadState(username=user.username, room_id=room_id)
        db.add(state)
    state.last_read_message_id = msg.id
    state.last_read_at = datetime.utcnow()

    db.commit()
    db.refresh(msg)
    return {"message": _serialize_message(msg)}


@router.post("/rooms/{room_id}/read")
def mark_read(
    room_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room or not _can_access_room(user, room):
        raise HTTPException(status_code=403, detail="Access denied")

    last = (
        db.query(func.max(ChatMessage.id))
        .filter(ChatMessage.room_id == room_id)
        .scalar()
    ) or 0

    state = (
        db.query(ChatReadState)
        .filter(ChatReadState.username == user.username, ChatReadState.room_id == room_id)
        .first()
    )
    if not state:
        state = ChatReadState(username=user.username, room_id=room_id)
        db.add(state)
    state.last_read_message_id = last
    state.last_read_at = datetime.utcnow()

    db.query(ChatNotification).filter(
        ChatNotification.username == user.username,
        ChatNotification.room_id == room_id,
        ChatNotification.is_read.is_(False),
    ).update({"is_read": True})

    db.commit()
    return {"ok": True, "last_read_message_id": last}


@router.get("/unread")
def unread_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rooms = db.query(ChatRoom).all()
    total = 0
    by_room = {}
    for room in rooms:
        if not _can_access_room(user, room):
            continue
        count = _unread_count(db, user.username, room.id)
        if count:
            by_room[room.id] = count
            total += count
    return {"total": total, "by_room": by_room}


@router.post("/private")
def get_or_create_private_room(
    data: PrivateRoomRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    other = data.username.strip()
    if not other or other == user.username:
        raise HTTPException(status_code=400, detail="Invalid user")

    target = db.query(User).filter(User.username == other).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    a, b = sorted([user.username, other])
    room = (
        db.query(ChatRoom)
        .filter(
            ChatRoom.room_type == "private",
            ChatRoom.participant_a == a,
            ChatRoom.participant_b == b,
        )
        .first()
    )
    if not room:
        room = ChatRoom(
            name=f"{user.username} ↔ {other}",
            room_type="private",
            participant_a=a,
            participant_b=b,
            created_by=user.username,
        )
        db.add(room)
        db.commit()
        db.refresh(room)

    return {
        "id": room.id,
        "name": room.name,
        "room_type": room.room_type,
        "participant_a": room.participant_a,
        "participant_b": room.participant_b,
    }


@router.post("/typing")
def set_typing(
    data: TypingRequest,
    user: User = Depends(get_current_user),
):
    key = f"{data.room_id}:{user.username}"
    if data.is_typing:
        _typing_state[key] = {
            "username": user.username,
            "room_id": data.room_id,
            "at": datetime.utcnow(),
        }
    else:
        _typing_state.pop(key, None)
    return {"ok": True}


@router.get("/typing/{room_id}")
def get_typing(
    room_id: int,
    user: User = Depends(get_current_user),
):
    cutoff = datetime.utcnow() - timedelta(seconds=TYPING_TTL_SECONDS)
    users = []
    for key, val in list(_typing_state.items()):
        if val["room_id"] != room_id:
            continue
        if val["at"] < cutoff:
            _typing_state.pop(key, None)
            continue
        if val["username"] != user.username:
            users.append(val["username"])
    return {"typing": users}


@router.get("/online")
def chat_online(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return {"operators": get_online_operators_detailed(db)}


@router.get("/users")
def list_chat_users(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    users = (
        db.query(User)
        .filter(User.is_active.isnot(False), User.username != user.username)
        .order_by(User.username)
        .all()
    )
    return [
        {
            "username": u.username,
            "department": u.department,
            "role": u.role,
        }
        for u in users
    ]


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    msg.content = "[O'chirildi — moderator]"
    msg.message_type = "deleted"
    db.commit()
    return {"message": _serialize_message(msg)}
