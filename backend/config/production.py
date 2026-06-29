"""Production startup validation helpers."""

from __future__ import annotations

import logging
import os
import re

from auth.security import get_secret_key, is_auth_configured

_log = logging.getLogger("azmus.production")

# Always allowed Velcore ERP frontends (explicit — never use * in production).
VELCORE_PRODUCTION_ORIGINS: tuple[str, ...] = (
    "https://erp.velcore.uz",
    "http://erp.velcore.uz",
)

# Common local dev / Flutter Web / Vite ports (merged when dev CORS is enabled).
VELCORE_DEV_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://localhost:5000",
    "http://localhost:5173",
    "http://localhost:54847",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:54847",
)

# Flutter Web / Vite pick random ports — regex covers any localhost port.
LOCALHOST_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"


def _is_production_env() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() == "production"


def cors_dev_origins_enabled() -> bool:
    """
    Allow localhost / Flutter Web origins against this API.

    Production: set CORS_ALLOW_DEV=true in /etc/velcore/.env when developers
    hit https://api.velcore.uz from local Flutter Web.
    Non-production: enabled by default.
    """
    flag = os.getenv("CORS_ALLOW_DEV", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    return not _is_production_env()


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def _merge_origins(origins: list[str], extra: tuple[str, ...]) -> None:
    existing = {o.lower() for o in origins}
    for item in extra:
        normalized = _normalize_origin(item)
        if normalized and normalized.lower() not in existing:
            origins.append(normalized)
            existing.add(normalized.lower())


def parse_cors_origins() -> list[str]:
    """
    Parse CORS_ORIGINS into an explicit allow-list.

    - ``*`` only in non-production (local dev). Production never uses wildcard.
    - Always merges Velcore ERP production frontends.
    - Merges localhost dev origins when ``cors_dev_origins_enabled()``.
    """
    raw = os.getenv("CORS_ORIGINS", "*").strip()
    origins: list[str] = []

    if raw == "*":
        if _is_production_env():
            _log.warning(
                "CORS_ORIGINS=* is not allowed in production; "
                "using explicit Velcore origins (and dev origins if CORS_ALLOW_DEV=true)"
            )
        else:
            return ["*"]
    else:
        origins = [_normalize_origin(o) for o in raw.split(",") if o.strip()]

    _merge_origins(origins, VELCORE_PRODUCTION_ORIGINS)
    if cors_dev_origins_enabled():
        _merge_origins(origins, VELCORE_DEV_ORIGINS)

    return origins


def get_cors_origin_regex() -> str | None:
    """Regex for dynamic localhost ports (Flutter Web, Vite)."""
    custom = os.getenv("CORS_ORIGIN_REGEX", "").strip()
    if custom:
        return custom
    if cors_dev_origins_enabled():
        return LOCALHOST_ORIGIN_REGEX
    return None


def cors_allow_credentials(origins: list[str]) -> bool:
    """Credentials require explicit origins — not compatible with ``*``."""
    return origins != ["*"]


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
    origins = parse_cors_origins()
    regex = get_cors_origin_regex()
    _log.info(
        "Effective DATABASE_URL=%s source=%s",
        mask_database_url(database_url),
        database_url_source,
    )
    _log.info(
        "Config: DATA_ROOT=%s JWT=%s ENV=%s CORS_ORIGINS=%s CORS_ALLOW_DEV=%s "
        "cors_origins_count=%s cors_regex=%s",
        os.getenv("DATA_ROOT", ""),
        "set" if is_auth_configured() else "MISSING",
        os.getenv("ENVIRONMENT", "development"),
        os.getenv("CORS_ORIGINS", "*"),
        cors_dev_origins_enabled(),
        len(origins) if origins != ["*"] else "*",
        regex or "(none)",
    )
    if origins != ["*"]:
        _log.info("CORS allow_origins: %s", ", ".join(origins))
