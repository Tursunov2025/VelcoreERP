"""
Central environment loading — single place for .env file priority.

Priority (highest wins for DATABASE_URL on Linux):
  1. Process environment (systemd EnvironmentFile, shell export)
  2. AZMUS_ENV_FILE (if set)
  3. /etc/velcore/.env, /etc/azmus/.env (override repo/backend .env on Linux)
  4. backend/.env, repo/.env (development gap-fill only)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent

VELCORE_ENV = Path("/etc/velcore/.env")
AZMUS_ENV = Path("/etc/azmus/.env")

LOADED_ENV_FILES: list[str] = []


def _load_file(path: Path, *, override: bool) -> None:
    if not path.is_file():
        return
    had_url = bool(os.getenv("DATABASE_URL"))
    previous_url = os.getenv("DATABASE_URL")
    load_dotenv(path, override=override)
    LOADED_ENV_FILES.append(f"{path} override={override}")
    current_url = os.getenv("DATABASE_URL")
    if not current_url:
        return
    if override or not had_url:
        os.environ["DATABASE_URL_SOURCE"] = str(path)
    elif not os.getenv("DATABASE_URL_SOURCE"):
        os.environ["DATABASE_URL_SOURCE"] = str(path)
    if had_url and not override and current_url != previous_url:
        # Another file already set DATABASE_URL; this file was ignored for that key.
        pass


def load_environment() -> None:
    """Load all configured env files once at process start."""
    if os.getenv("DATABASE_URL"):
        os.environ.setdefault("DATABASE_URL_SOURCE", "process environment")

    explicit = os.getenv("AZMUS_ENV_FILE", "").strip()

    dev_chain: list[Path] = [_REPO_ROOT / ".env", _BACKEND_DIR / ".env"]
    if os.name == "nt":
        dev_chain = [
            Path(r"D:\AzmusERP\Application\backend\.env"),
            Path(r"D:\AzmusERP\Application\.env"),
            Path(r"D:\AzmusERP\.env"),
            *dev_chain,
        ]

    for path in dev_chain:
        _load_file(path, override=False)

    # Linux VPS: system env must override stale DATABASE_URL in repo/backend/.env
    if sys.platform != "win32":
        for path in (AZMUS_ENV, VELCORE_ENV):
            _load_file(path, override=True)

    if explicit:
        _load_file(Path(explicit), override=True)


def get_database_url_source() -> str:
    return os.getenv("DATABASE_URL_SOURCE", "unset")


def audit_env_loading(logger) -> None:
    if LOADED_ENV_FILES:
        logger.info("Env files loaded: %s", " -> ".join(LOADED_ENV_FILES))
    logger.info("DATABASE_URL source: %s", get_database_url_source())
