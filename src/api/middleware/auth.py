"""JWT authentication middleware, token verification, and RBAC.

Supports RS256 (production) with HS256 fallback (local_fallback mode).
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from src.api.schemas.auth import UserInfo
from src.core.settings import AuthSettings, Settings

logger = logging.getLogger("chipwise.auth")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# JWT constants
JWT_ISSUER = "chipwise-enterprise"
JWT_AUDIENCE = "chipwise-api"

# Paths that do NOT require authentication
PUBLIC_PATHS = {"/health", "/readiness", "/docs", "/openapi.json", "/redoc"}


# ── Token creation ──────────────────────────────────────────────────


def create_access_token(
    payload: dict[str, Any],
    settings: AuthSettings,
    expire_minutes: int | None = None,
) -> str:
    """Create a signed JWT access token."""
    now = time.time()
    exp_minutes = expire_minutes or settings.jwt.access_token_expire_minutes
    claims = {
        **payload,
        "iat": int(now),
        "exp": int(now + exp_minutes * 60),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "type": "access",
    }
    key, algorithm = _get_signing_key(settings)
    return jwt.encode(claims, key, algorithm=algorithm)


def create_refresh_token(
    payload: dict[str, Any],
    settings: AuthSettings,
) -> str:
    """Create a signed JWT refresh token."""
    now = time.time()
    exp_days = settings.jwt.refresh_token_expire_days
    claims = {
        **payload,
        "iat": int(now),
        "exp": int(now + exp_days * 86400),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "type": "refresh",
    }
    key, algorithm = _get_signing_key(settings)
    return jwt.encode(claims, key, algorithm=algorithm)


# ── Token verification ──────────────────────────────────────────────


def verify_jwt_token(token: str, settings: AuthSettings) -> dict[str, Any]:
    """Verify JWT signature, expiry, issuer, and audience.

    Returns:
        Decoded claims dict.

    Raises:
        HTTPException(401) on any verification failure.
    """
    key, algorithm = _get_verification_key(settings)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            issuer=JWT_ISSUER,
            audience=JWT_AUDIENCE,
        )
        return claims
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI Depends ─────────────────────────────────────────────────


def _get_auth_settings() -> AuthSettings:
    """Import-time safe accessor for auth settings."""
    from src.api.dependencies import get_settings

    return get_settings().auth


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
) -> UserInfo:
    """FastAPI dependency: extract and validate current user from JWT.

    Raises:
        HTTPException(401) if token is missing or invalid.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    auth_settings = _get_auth_settings()
    claims = verify_jwt_token(token, auth_settings)

    return UserInfo(
        sub=claims.get("sub", ""),
        username=claims.get("username", ""),
        role=claims.get("role", "user"),
        department=claims.get("department", ""),
    )


# ── RBAC decorator ──────────────────────────────────────────────────


def require_role(*roles: str) -> Callable:
    """Dependency factory that checks user role against allowed roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
    """

    async def role_checker(
        current_user: UserInfo = Depends(get_current_user),
    ) -> UserInfo:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role}' not permitted. Required: {roles}",
            )
        return current_user

    return role_checker


# ── Key management ──────────────────────────────────────────────────


def _get_signing_key(settings: AuthSettings) -> tuple[str, str]:
    """Return (key, algorithm) for signing tokens.

    Uses RS256 with private key file if available, falls back to HS256.
    """
    if settings.local_fallback.enabled and settings.local_fallback.jwt_secret:
        return settings.local_fallback.jwt_secret, "HS256"

    # RS256: load private key from file
    import pathlib

    pk_path = pathlib.Path(settings.jwt.private_key_path)
    if pk_path.exists():
        return pk_path.read_text(), settings.jwt.algorithm

    # Fallback to HS256 if no RS256 key is available
    if settings.local_fallback.jwt_secret:
        return settings.local_fallback.jwt_secret, "HS256"

    raise RuntimeError("No JWT signing key configured (set JWT_SECRET_KEY or provide RSA keys)")


def _get_verification_key(settings: AuthSettings) -> tuple[str, str]:
    """Return (key, algorithm) for verifying tokens."""
    if settings.local_fallback.enabled and settings.local_fallback.jwt_secret:
        return settings.local_fallback.jwt_secret, "HS256"

    import pathlib

    pub_path = pathlib.Path(settings.jwt.public_key_path)
    if pub_path.exists():
        return pub_path.read_text(), settings.jwt.algorithm

    if settings.local_fallback.jwt_secret:
        return settings.local_fallback.jwt_secret, "HS256"

    raise RuntimeError("No JWT verification key configured")
