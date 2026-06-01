import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth.deps import get_current_user, require_admin
from database import get_db
from models import User
from schemas import AdminTelegramLink, TelegramVerifyLink

router = APIRouter(prefix="/telegram", tags=["telegram"])


class LinkCodeResponse(BaseModel):
    code: str
    expires_in_minutes: int
    instructions: str


@router.get("/status")
def telegram_link_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {
        "linked": bool(user.telegram_id),
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username or "",
        "has_pending_code": bool(
            user.telegram_link_code
            and user.telegram_link_code_expires
            and user.telegram_link_code_expires > datetime.utcnow()
        ),
    }


@router.post("/link-code", response_model=LinkCodeResponse)
def generate_link_code(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    code = secrets.token_hex(3).upper()[:6]
    user.telegram_link_code = code
    user.telegram_link_code_expires = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    return LinkCodeResponse(
        code=code,
        expires_in_minutes=15,
        instructions=(
            "Telegram botga shu kodni yuboring yoki quyidagi forma orqali "
            "Telegram ID va username ni tasdiqlang."
        ),
    )


@router.post("/verify-link")
def verify_telegram_link(
    data: TelegramVerifyLink,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.telegram_link_code:
        raise HTTPException(status_code=400, detail="Avval kod oling")
    if not user.telegram_link_code_expires or user.telegram_link_code_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Kod muddati tugagan")
    if data.code.strip().upper() != user.telegram_link_code.upper():
        raise HTTPException(status_code=400, detail="Noto'g'ri kod")

    user.telegram_id = data.telegram_id.strip()
    user.telegram_username = (data.telegram_username or "").strip().lstrip("@")
    user.telegram_link_code = None
    user.telegram_link_code_expires = None
    db.commit()
    return {
        "message": "Telegram bog'landi",
        "telegram_id": user.telegram_id,
        "telegram_username": user.telegram_username,
    }


@router.post("/unlink")
def unlink_telegram(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.telegram_id = None
    user.telegram_username = None
    user.telegram_link_code = None
    user.telegram_link_code_expires = None
    db.commit()
    return {"message": "Telegram uzildi"}


@router.put("/admin/users/{user_id}/telegram")
def admin_set_user_telegram(
    user_id: int,
    data: AdminTelegramLink,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    target.telegram_id = data.telegram_id.strip()
    target.telegram_username = (data.telegram_username or "").strip().lstrip("@")
    db.commit()
    return {
        "user_id": target.id,
        "telegram_id": target.telegram_id,
        "telegram_username": target.telegram_username,
    }
