from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth.deps import get_current_user
from services.activity import record_login
from services.permissions import get_user_permissions
from auth.security import (
    AuthNotConfiguredError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_auth_configured,
    verify_password,
)
from database import get_db
from models import User
from schemas import (
    LoginRequest,
    LoginUserOption,
    RefreshRequest,
    TokenResponse,
    UserPublic,
    UserUiPreferencesUpdate,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None

    if user.is_active is False:
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
    try:
        return TokenResponse(
            access_token=create_access_token(data),
            refresh_token=create_refresh_token(data),
            username=user.username,
            role=user.role,
            department=dept,
        )
    except AuthNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/login-users", response_model=list[LoginUserOption])
def login_users(db: Session = Depends(get_db)):
    """Public list of usernames for the login screen (no auth required)."""
    return (
        db.query(User)
        .filter(User.is_active.is_(True))
        .order_by(User.username)
        .all()
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = _authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login yoki parol xato",
        )
    record_login(db, user)
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


@router.get("/me/permissions")
def my_permissions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return {"permissions": get_user_permissions(db, user)}


@router.get("/me/ui-preferences")
def get_ui_preferences(user: User = Depends(get_current_user)):
    return {
        "ui_language": user.ui_language,
        "ui_theme": user.ui_theme,
        "ui_clock_format": user.ui_clock_format,
    }


@router.put("/me/ui-preferences")
def update_ui_preferences(
    data: UserUiPreferencesUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if data.ui_language is not None:
        user.ui_language = data.ui_language
    if data.ui_theme is not None:
        user.ui_theme = data.ui_theme
    if data.ui_clock_format is not None:
        user.ui_clock_format = data.ui_clock_format
    db.commit()
    db.refresh(user)
    return {
        "ui_language": user.ui_language,
        "ui_theme": user.ui_theme,
        "ui_clock_format": user.ui_clock_format,
    }
