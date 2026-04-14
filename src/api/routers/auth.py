"""Auth router: register + login endpoints (local fallback mode)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.api.middleware.auth import (
    create_access_token,
    create_refresh_token,
)
from src.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
)

logger = logging.getLogger("chipwise.auth")

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# In-memory user store (Phase 1 only — replaced by PG in Phase 3+)
_users: dict[str, dict[str, Any]] = {}


def _hash_password(password: str) -> str:
    """Hash password using bcrypt if available, fallback to SHA256."""
    try:
        import bcrypt

        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        # Fallback for environments without bcrypt
        return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored hash."""
    try:
        import bcrypt

        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ImportError:
        return hashlib.sha256(password.encode()).hexdigest() == hashed


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest) -> TokenResponse:
    """Register a new user and return JWT tokens."""
    if req.username in _users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{req.username}' already exists",
        )

    hashed = _hash_password(req.password)
    _users[req.username] = {
        "username": req.username,
        "password_hash": hashed,
        "email": req.email,
        "department": req.department,
        "role": req.role,
    }
    logger.info("User registered: %s (role=%s)", req.username, req.role)

    return _issue_tokens(req.username, req.role, req.department)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    """Authenticate user and return JWT tokens."""
    user = _users.get(req.username)
    if user is None or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    logger.info("User logged in: %s", req.username)
    return _issue_tokens(user["username"], user["role"], user.get("department", ""))


def _issue_tokens(username: str, role: str, department: str) -> TokenResponse:
    """Create access + refresh tokens for a user."""
    from src.api.dependencies import get_settings

    settings = get_settings()
    payload = {
        "sub": username,
        "username": username,
        "role": role,
        "department": department,
    }
    access = create_access_token(payload, settings.auth)
    refresh = create_refresh_token(payload, settings.auth)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.auth.jwt.access_token_expire_minutes * 60,
    )
