"""Production startup validation helpers."""

from __future__ import annotations

import logging
import os
import re

from auth.security import get_secret_key, is_auth_configured

_log = logging.getLogger("azmus.production")


def mask_database_url(url: str) -> str:
    """Return DATABASE_URL with password redacted for logs."""
    if not url:
        return "(empty)"
    if url.startswith("sqlite"):
        return url
    # postgresql+psycopg2://user:password@host:port/db
    masked = re.sub(
        r"(://[^:/@]+:)([^@]+)(@)",
        r"\1****\3",
        url,
        count=1,
    )
    return masked


def parse_cors_origins() -> list[str]:
    """Parse CORS_ORIGINS; always allow Velcore ERP frontend in production."""
    raw = os.getenv("CORS_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    for required in (
        "https://erp.velcore.uz",
        "http://erp.velcore.uz",
    ):
        if required not in origins:
            origins.append(required)
    return origins


def validate_runtime_config() -> list[str]:
    """Return list of fatal configuration errors (empty = OK)."""
    errors: list[str] = []
    if not (os.getenv("DATABASE_URL") or "").strip():
        errors.append("DATABASE_URL is not set")
    if not is_auth_configured():
        errors.append("JWT_SECRET_KEY is not set (check /etc/velcore/.env)")
    jwt = get_secret_key()
    if jwt and len(jwt) < 16:
        errors.append("JWT_SECRET_KEY is too short (use at least 32 characters)")
    return errors


def log_effective_config(database_url: str, database_url_source: str) -> None:
    """Log effective configuration at startup (secrets masked)."""
    _log.info(
        "Effective DATABASE_URL=%s source=%s",
        mask_database_url(database_url),
        database_url_source,
    )
    _log.info(
        "Config: DATA_ROOT=%s JWT=%s CORS=%s ENV=%s",
        os.getenv("DATA_ROOT", ""),
        "set" if is_auth_configured() else "MISSING",
        os.getenv("CORS_ORIGINS", "*"),
        os.getenv("ENVIRONMENT", "development"),
    )
