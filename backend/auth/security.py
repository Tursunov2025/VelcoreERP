import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger("azmus.auth")

SECRET_KEY = (os.getenv("JWT_SECRET_KEY") or "").strip()
if not SECRET_KEY:
    logger.error(
        "JWT_SECRET_KEY is not set. The API will start, but login and JWT auth are disabled "
        "until JWT_SECRET_KEY is configured in the environment."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


class AuthNotConfiguredError(RuntimeError):
    """Raised when JWT operations are attempted without JWT_SECRET_KEY."""


def is_auth_configured() -> bool:
    return bool(SECRET_KEY)


def _require_secret_key() -> str:
    if not SECRET_KEY:
        raise AuthNotConfiguredError(
            "JWT_SECRET_KEY is not configured. Set it in Render environment variables."
        )
    return SECRET_KEY


def _normalize_password(password: str) -> bytes:
    """Bcrypt accepts at most 72 bytes."""
    return password.encode("utf-8")[:72]


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            _normalize_password(plain),
            hashed.encode("utf-8"),
        )
    except Exception:
        return False


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        _normalize_password(password),
        bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    secret = _require_secret_key()
    payload = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    secret = _require_secret_key()
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    if not SECRET_KEY:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
