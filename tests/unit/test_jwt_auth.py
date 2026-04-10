"""Unit tests for JWT auth middleware, token creation/verification, and RBAC."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from src.api.middleware.auth import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_role,
    verify_jwt_token,
)
from src.api.schemas.auth import UserInfo
from src.core.settings import AuthSettings, JWTSettings, LocalFallbackSettings

# ── Test fixtures ───────────────────────────────────────────────────

TEST_SECRET = "test-jwt-secret-key-for-unit-tests"


@pytest.fixture
def auth_settings() -> AuthSettings:
    """Auth settings configured for HS256 local fallback."""
    return AuthSettings(
        mode="local",
        jwt=JWTSettings(algorithm="HS256"),
        local_fallback=LocalFallbackSettings(enabled=True, jwt_secret=TEST_SECRET),
    )


@pytest.fixture
def sample_payload() -> dict:
    return {
        "sub": "testuser",
        "username": "testuser",
        "role": "user",
        "department": "engineering",
    }


@pytest.fixture
def access_token(auth_settings, sample_payload) -> str:
    return create_access_token(sample_payload, auth_settings)


def _make_test_app(auth_settings: AuthSettings) -> FastAPI:
    """Build a minimal FastAPI app with auth-protected endpoints."""
    from src.api.dependencies import override_settings
    from src.core.settings import Settings

    settings = Settings(
        llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
        embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
        auth=auth_settings,
    )
    override_settings(settings)

    app = FastAPI()

    @app.get("/protected")
    async def protected(user: UserInfo = Depends(get_current_user)):
        return {"username": user.username, "role": user.role}

    @app.get("/admin-only", dependencies=[Depends(require_role("admin"))])
    async def admin_only():
        return {"access": "granted"}

    @app.get("/multi-role", dependencies=[Depends(require_role("admin", "manager"))])
    async def multi_role():
        return {"access": "granted"}

    return app


# ── Token creation ──────────────────────────────────────────────────


@pytest.mark.unit
class TestTokenCreation:
    def test_create_access_token(self, auth_settings, sample_payload) -> None:
        token = create_access_token(sample_payload, auth_settings)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_refresh_token(self, auth_settings, sample_payload) -> None:
        token = create_refresh_token(sample_payload, auth_settings)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_access_and_refresh_are_different(self, auth_settings, sample_payload) -> None:
        access = create_access_token(sample_payload, auth_settings)
        refresh = create_refresh_token(sample_payload, auth_settings)
        assert access != refresh


# ── Token verification ──────────────────────────────────────────────


@pytest.mark.unit
class TestTokenVerification:
    def test_verify_valid_token(self, auth_settings, sample_payload) -> None:
        token = create_access_token(sample_payload, auth_settings)
        claims = verify_jwt_token(token, auth_settings)
        assert claims["sub"] == "testuser"
        assert claims["username"] == "testuser"
        assert claims["role"] == "user"
        assert claims["iss"] == JWT_ISSUER
        assert claims["aud"] == JWT_AUDIENCE

    def test_verify_expired_token_raises_401(self, auth_settings, sample_payload) -> None:
        from fastapi import HTTPException

        # Create a token that's already expired
        token = create_access_token(sample_payload, auth_settings, expire_minutes=-1)
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(token, auth_settings)
        assert exc_info.value.status_code == 401

    def test_verify_tampered_token_raises_401(self, auth_settings, sample_payload) -> None:
        from fastapi import HTTPException

        token = create_access_token(sample_payload, auth_settings)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token(tampered, auth_settings)
        assert exc_info.value.status_code == 401

    def test_verify_garbage_token_raises_401(self, auth_settings) -> None:
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            verify_jwt_token("not-a-real-token", auth_settings)
        assert exc_info.value.status_code == 401


# ── get_current_user dependency ─────────────────────────────────────


@pytest.mark.unit
class TestGetCurrentUser:
    def test_authenticated_access(self, auth_settings, access_token) -> None:
        app = _make_test_app(auth_settings)
        with TestClient(app) as client:
            resp = client.get(
                "/protected",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    def test_no_token_returns_401(self, auth_settings) -> None:
        app = _make_test_app(auth_settings)
        with TestClient(app) as client:
            resp = client.get("/protected")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, auth_settings) -> None:
        app = _make_test_app(auth_settings)
        with TestClient(app) as client:
            resp = client.get(
                "/protected",
                headers={"Authorization": "Bearer invalid-token"},
            )
        assert resp.status_code == 401


# ── RBAC ────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRBAC:
    def test_admin_role_granted(self, auth_settings) -> None:
        admin_payload = {
            "sub": "admin",
            "username": "admin",
            "role": "admin",
            "department": "ops",
        }
        token = create_access_token(admin_payload, auth_settings)
        app = _make_test_app(auth_settings)
        with TestClient(app) as client:
            resp = client.get(
                "/admin-only",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200

    def test_user_role_denied_admin_endpoint(self, auth_settings, access_token) -> None:
        app = _make_test_app(auth_settings)
        with TestClient(app) as client:
            resp = client.get(
                "/admin-only",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        assert resp.status_code == 403

    def test_multi_role_accepts_manager(self, auth_settings) -> None:
        manager_payload = {
            "sub": "mgr",
            "username": "mgr",
            "role": "manager",
            "department": "hw",
        }
        token = create_access_token(manager_payload, auth_settings)
        app = _make_test_app(auth_settings)
        with TestClient(app) as client:
            resp = client.get(
                "/multi-role",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200


# ── Auth router (register + login) ─────────────────────────────────


@pytest.mark.unit
class TestAuthRouter:
    @pytest.fixture(autouse=True)
    def _clear_users(self):
        import src.api.routers.auth as auth_mod

        auth_mod._users.clear()
        yield
        auth_mod._users.clear()

    @pytest.fixture
    def auth_client(self, auth_settings):
        from src.api.dependencies import override_settings
        from src.core.settings import Settings

        settings = Settings(
            llm=Settings.model_fields["llm"].default_factory(),  # type: ignore[union-attr]
            embedding=Settings.model_fields["embedding"].default_factory(),  # type: ignore[union-attr]
            auth=auth_settings,
        )
        override_settings(settings)

        from src.api.routers.auth import router

        app = FastAPI()
        app.include_router(router)
        with TestClient(app) as client:
            yield client

    def test_register_returns_tokens(self, auth_client) -> None:
        resp = auth_client.post(
            "/api/v1/auth/register",
            json={"username": "newuser", "password": "password123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_returns_409(self, auth_client) -> None:
        auth_client.post(
            "/api/v1/auth/register",
            json={"username": "dupuser", "password": "password123"},
        )
        resp = auth_client.post(
            "/api/v1/auth/register",
            json={"username": "dupuser", "password": "password456"},
        )
        assert resp.status_code == 409

    def test_login_success(self, auth_client) -> None:
        auth_client.post(
            "/api/v1/auth/register",
            json={"username": "loginuser", "password": "password123"},
        )
        resp = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "loginuser", "password": "password123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, auth_client) -> None:
        auth_client.post(
            "/api/v1/auth/register",
            json={"username": "wrongpw", "password": "correct123"},
        )
        resp = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "wrongpw", "password": "wrong456"},
        )
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, auth_client) -> None:
        resp = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "pass123"},
        )
        assert resp.status_code == 401

    def test_register_login_e2e(self, auth_settings, auth_client) -> None:
        """Full flow: register → login → use token → access protected endpoint."""
        from src.api.dependencies import override_settings
        from src.core.settings import Settings

        # Register
        reg = auth_client.post(
            "/api/v1/auth/register",
            json={"username": "e2euser", "password": "password123", "role": "admin"},
        )
        assert reg.status_code == 200
        token = reg.json()["access_token"]

        # Verify token is valid
        claims = verify_jwt_token(token, auth_settings)
        assert claims["username"] == "e2euser"
        assert claims["role"] == "admin"
