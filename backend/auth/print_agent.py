"""API key auth for local cloud print agents."""

import os

from fastapi import Header, HTTPException, status

PRINT_AGENT_API_KEY = os.getenv("PRINT_AGENT_API_KEY", "").strip()


def require_print_agent(authorization: str | None = Header(default=None)) -> None:
    if not PRINT_AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PRINT_AGENT_API_KEY is not configured on the server",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing print agent bearer token",
        )
    token = authorization[7:].strip()
    if token != PRINT_AGENT_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid print agent API key",
        )
