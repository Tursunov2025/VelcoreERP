from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from database import get_db
from models import User
from schemas import LoginRequest, RefreshRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    if user.password_hash:
        if verify_password(password, user.password_hash):
            return user
        return None

    if user.password and user.password == password:
        user.password_hash = hash_password(password)
        user.password = None
        db.commit()
        return user

    return None


def _token_response(user: User) -> TokenResponse:
    dept = user.department or ("Admin" if user.role == "admin" else "Kesish")
    data = {"sub": user.username, "role": user.role, "department": dept}
    return TokenResponse(
        access_token=create_access_token(data),
        refresh_token=create_refresh_token(data),
        username=user.username,
        role=user.role,
        department=dept,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = _authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol xato",
        )
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return _token_response(user)


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return user
