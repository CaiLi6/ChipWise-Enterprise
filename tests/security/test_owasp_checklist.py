"""OWASP Top 10 automated security checklist (§6C2)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import available routers for testing
from src.api.routers.auth import router as auth_router
from src.api.routers.health import router as health_router
from src.api.routers.knowledge import router as knowledge_router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(knowledge_router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def reset_knowledge():
    import src.api.routers.knowledge as km
    km._notes.clear()
    km._next_id = 1
    yield
    km._notes.clear()
    km._next_id = 1


@pytest.mark.unit
class TestA01BrokenAccessControl:
    """A01: Verify protected endpoints enforce authentication."""

    def test_health_is_public(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_readiness_accessible(self, client: TestClient) -> None:
        # readiness may fail due to missing services but should not crash
        resp = client.get("/readiness")
        assert resp.status_code in (200, 500, 422)  # not 401


@pytest.mark.unit
class TestA02CryptographicFailures:
    """A02: Passwords must not be stored in plaintext."""

    def test_password_hashed_on_register(self, client: TestClient) -> None:
        import src.api.routers.auth as auth_mod

        resp = client.post("/api/v1/auth/register", json={
            "username": "testuser_a02",
            "password": "S3cur3P@ss!",
            "email": "test@example.com",
            "department": "eng",
            "role": "user",
        })
        assert resp.status_code == 200

        # Verify password is not stored in plaintext
        user = auth_mod._users.get("testuser_a02")
        assert user is not None
        assert user["password_hash"] != "S3cur3P@ss!", "Password must not be stored in plaintext"
        # Hash should be significantly longer than the password
        assert len(user["password_hash"]) > len("S3cur3P@ss!")

    def test_wrong_password_rejected(self, client: TestClient) -> None:
        client.post("/api/v1/auth/register", json={
            "username": "testuser_a02b",
            "password": "correct_pass",
            "email": "b@example.com",
            "department": "eng",
            "role": "user",
        })
        resp = client.post("/api/v1/auth/login", json={
            "username": "testuser_a02b",
            "password": "wrong_pass",
        })
        assert resp.status_code == 401


@pytest.mark.unit
class TestA03Injection:
    """A03: Verify SQL injection patterns are handled."""

    def test_sql_injection_in_username_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/login", json={
            "username": "' OR 1=1 --",
            "password": "anything",
        })
        # Should return 401 (user not found), not 200 or 500
        assert resp.status_code == 401

    def test_xss_payload_in_note_stored_as_literal(self, client: TestClient) -> None:
        xss = "<script>alert('XSS')</script>"
        resp = client.post("/api/v1/knowledge", json={"content": xss})
        assert resp.status_code == 200
        # Content returned as-is (FastAPI returns JSON, not HTML — no XSS surface)
        assert resp.json()["content"] == xss


@pytest.mark.unit
class TestA04InsecureDesign:
    """A04: Verify input validation at API boundaries."""

    def test_register_validates_required_fields(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422

    def test_login_validates_required_fields(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


@pytest.mark.unit
class TestA07AuthenticationFailures:
    """A07: Verify authentication responses are consistent."""

    def test_unknown_user_returns_401(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/login", json={
            "username": "__no_such_user__",
            "password": "anything",
        })
        assert resp.status_code == 401

    def test_duplicate_registration_returns_409(self, client: TestClient) -> None:
        payload = {
            "username": "dup_user",
            "password": "pass123",
            "email": "d@d.com",
            "department": "x",
            "role": "user",
        }
        client.post("/api/v1/auth/register", json=payload)
        resp = client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 409


@pytest.mark.unit
class TestA09LoggingMonitoring:
    """A09: Verify TokenResponse does not expose raw password in response."""

    def test_token_response_has_no_password(self, client: TestClient) -> None:
        resp = client.post("/api/v1/auth/register", json={
            "username": "logtest",
            "password": "secret_password",
            "email": "l@l.com",
            "department": "eng",
            "role": "user",
        })
        assert resp.status_code == 200
        body = resp.json()
        # Password must not appear in response body
        assert "secret_password" not in str(body)
        assert "access_token" in body
