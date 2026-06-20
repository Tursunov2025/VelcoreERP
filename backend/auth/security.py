import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

logger = logging.getLogger("azmus.auth")

ALGORITHM = "HS256"


def get_secret_key() -> str:
    """Read JWT secret at call time so /etc/velcore/.env loads before auth runs."""
    return (os.getenv("JWT_SECRET_KEY") or "").strip()


def _env_access_minutes() -> int | None:
    raw = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_refresh_days() -> int | None:
    raw = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_access_token_expire_minutes() -> int:
    env = _env_access_minutes()
    if env is not None:
        return env
    from services.settings_cache import get_cached_int

    return get_cached_int("jwt_access_minutes", 60)


def get_refresh_token_expire_days() -> int:
    env = _env_refresh_days()
    if env is not None:
        return env
    from services.settings_cache import get_cached_int

    return get_cached_int("jwt_refresh_days", 7)


class AuthNotConfiguredError(RuntimeError):
    """Raised when JWT operations are attempted without JWT_SECRET_KEY."""


def is_auth_configured() -> bool:
    return bool(get_secret_key())


def _require_secret_key() -> str:
    secret = get_secret_key()
    if not secret:
        raise AuthNotConfiguredError(
            "JWT_SECRET_KEY is not configured. Set it in /etc/velcore/.env or the process environment."
        )
    return secret


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
        expires_delta or timedelta(minutes=get_access_token_expire_minutes())
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    secret = _require_secret_key()
    payload = data.copy()
    expire = datetime.utcnow() + timedelta(days=get_refresh_token_expire_days())
    payload.update({"exp": expire, "type": "refresh"})
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    secret = get_secret_key()
    if not secret:
        return None
    try:
        return jwt.decode(token, secret, algorithms=[ALGORITHM])
    except JWTError:
        return None
