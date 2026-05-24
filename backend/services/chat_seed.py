from constants import DEPARTMENTS
from models import ChatRoom


def seed_chat_rooms(db):
    if not db.query(ChatRoom).filter(ChatRoom.room_type == "announcement").first():
        db.add(
            ChatRoom(
                name="E'lonlar",
                room_type="announcement",
                department="Admin",
                created_by="system",
            )
        )

    for dept in DEPARTMENTS:
        existing = (
            db.query(ChatRoom)
            .filter(ChatRoom.room_type == "department", ChatRoom.department == dept)
            .first()
        )
        if not existing:
            db.add(
                ChatRoom(
                    name=f"{dept} bo'limi",
                    room_type="department",
                    department=dept,
                    created_by="system",
                )
            )

    db.commit()
