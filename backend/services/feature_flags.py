"""Environment feature flags for optional Phase 9/10 behavior."""

from __future__ import annotations

import os


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def traceability_enabled() -> bool:
    return _env_truthy("TRACEABILITY_ENABLED", "false")


def print_agent_enabled() -> bool:
    return _env_truthy("PRINT_AGENT_ENABLED", "false")
