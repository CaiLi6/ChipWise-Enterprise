"""Auth router: register + login endpoints backed by PostgreSQL."""

from __future__ import annotations

import hashlib
import logging
import os

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


def _pg_conn():
    """Return a psycopg2 connection using settings or env vars."""
    try:
        import psycopg2

        from src.api.dependencies import get_settings
        db = get_settings().database
        return psycopg2.connect(
            host=db.host,
            port=db.port,
            dbname=db.database,
            user=db.user,
            password=os.environ.get("PG_PASSWORD", db.password),
        )
    except Exception:
        return None


def _hash_password(password: str) -> str:
    """Hash password using bcrypt if available, fallback to SHA256."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    except ImportError:
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
    """Register a new user, persisted in PostgreSQL."""
    hashed = _hash_password(req.password)
    conn = _pg_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE username = %s", (req.username,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"User '{req.username}' already exists",
                )
            cur.execute(
                """INSERT INTO users (username, email, password_hash, role, department, is_active)
                   VALUES (%s, %s, %s, %s, %s, true)""",
                (req.username, req.email or f"{req.username}@chipwise.local",
                 hashed, req.role, req.department),
            )
            conn.commit()
        finally:
            conn.close()
    else:
        raise HTTPException(status_code=503, detail="Database unavailable")

    logger.info("User registered: %s (role=%s)", req.username, req.role)
    return _issue_tokens(req.username, req.role, req.department)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    """Authenticate user against PostgreSQL."""
    conn = _pg_conn()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, password_hash, role, department FROM users"
                " WHERE username = %s AND is_active = true",
                (req.username,),
            )
            row = cur.fetchone()
            cur.execute(
                "UPDATE users SET last_login_at = now() WHERE username = %s",
                (req.username,),
            )
            conn.commit()
        finally:
            conn.close()
    else:
        raise HTTPException(status_code=503, detail="Database unavailable")

    if row is None or not _verify_password(req.password, row[1]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    username, _, role, department = row
    logger.info("User logged in: %s", username)
    return _issue_tokens(username, role, department or "")


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
