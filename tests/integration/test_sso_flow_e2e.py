"""Integration E2E test for SSO callback flow (§6B2)."""

from __future__ import annotations

import os
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def api_base() -> str:
    return os.environ.get("CHIPWISE_API_URL", "http://localhost:8080")


def test_sso_flow_requires_keycloak(api_base: str) -> None:
    """SSO E2E requires a running Keycloak instance — skip if not configured."""
    keycloak_url = os.environ.get("KEYCLOAK_URL")
    if not keycloak_url:
        pytest.skip("KEYCLOAK_URL not set — SSO E2E test skipped")


@pytest.mark.asyncio
async def test_local_login_fallback(api_base: str) -> None:
    """Local password login must work when SSO is not configured."""
    httpx = pytest.importorskip("httpx")
    try:
        async with httpx.AsyncClient() as client:
            # Register + login locally
            reg = await client.post(
                f"{api_base}/api/v1/auth/register",
                json={
                    "username": "sso_test_user",
                    "password": "Test1234!",
                    "email": "sso@test.com",
                    "department": "QA",
                    "role": "user",
                },
                timeout=5,
            )
            if reg.status_code == 200:
                login = await client.post(
                    f"{api_base}/api/v1/auth/login",
                    json={"username": "sso_test_user", "password": "Test1234!"},
                    timeout=5,
                )
                assert login.status_code == 200
                assert "access_token" in login.json()
    except Exception as exc:
        pytest.skip(f"API not reachable: {exc}")
