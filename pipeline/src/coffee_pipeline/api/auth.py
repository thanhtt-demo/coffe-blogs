"""API key authentication dependency for the Pipeline Webapp API.

Reads WEBAPP_API_KEY from environment. Mutating endpoints (POST, PUT, DELETE)
must include header: Authorization: Bearer {key}
"""

from __future__ import annotations

import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer(auto_error=False)


def _get_expected_key() -> str:
    """Return the expected API key from environment."""
    return os.environ.get("WEBAPP_API_KEY", "")


async def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """FastAPI dependency that enforces Bearer-token auth on mutating requests.

    GET requests pass through without authentication.
    POST / PUT / DELETE require a valid ``Authorization: Bearer <key>`` header
    whose value matches the ``WEBAPP_API_KEY`` environment variable.

    Raises:
        HTTPException 401 – missing header, wrong key, or bad format.
    """
    # Read-only methods are public
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    auth_header = request.headers.get("Authorization")

    if auth_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    # Validate Bearer format
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
        )

    token = parts[1]
    expected = _get_expected_key()

    if not expected or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
