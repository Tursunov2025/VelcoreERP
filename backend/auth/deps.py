from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session

from auth.security import decode_token
from constants import user_can_access_stage
from database import get_db
from models import User
from services.activity import touch_activity
from services.permissions import user_has_permission

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials=Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deactivated",
        )

    try:
        touch_activity(db, user)
    except Exception:
        pass

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin" and user.department != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


def require_department_access(stage: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        dept = user.department or "Admin"
        if not user_can_access_stage(dept, user.role, stage):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No access to {stage} department",
            )
        return user

    return checker


def require_permission(key: str):
    def checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not user_has_permission(db, user, key):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {key}",
            )
        return user

    return checker

