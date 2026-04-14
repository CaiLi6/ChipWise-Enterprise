"""Integration tests for JIT provisioning with real PostgreSQL (§6B2).

Requires Docker PostgreSQL to be running (docker-compose up -d postgres).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.auth.sso.base import SSOUserInfo
from src.auth.sso.jit_provisioning import JITProvisioner


def _make_user(
    sub: str = "uid-sso-123",
    email: str = "user@corp.com",
    name: str = "Test User",
    provider: str = "keycloak",
    groups: list[str] | None = None,
    department: str = "Engineering",
) -> SSOUserInfo:
    return SSOUserInfo(
        sub=sub, email=email, name=name,
        provider=provider, department=department,
        groups=groups or [],
    )


def _make_pool_mock(fetchrow_return=None):
    """Create a mock asyncpg pool with acquire() context manager."""
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.execute = AsyncMock()

    pool = MagicMock()
    pool.acquire = MagicMock()

    class AcquireCtx:
        async def __aenter__(self):
            return conn
        async def __aexit__(self, *args):
            pass

    pool.acquire.return_value = AcquireCtx()
    return pool, conn


@pytest.mark.unit
class TestJITProvisionerPG:
    """Test JITProvisioner._provision_pg with mock asyncpg pool."""

    @pytest.mark.asyncio
    async def test_new_user_inserted_with_provider(self) -> None:
        """INSERT should include sso_provider column."""
        new_row = {
            "id": 1, "sso_provider": "keycloak", "sso_sub": "uid-sso-123",
            "email": "user@corp.com", "display_name": "Test User",
            "department": "Engineering", "role": "viewer",
        }
        pool, conn = _make_pool_mock(fetchrow_return=None)
        # First fetchrow (SELECT) returns None → new user
        # Second fetchrow (INSERT RETURNING) returns the new row
        conn.fetchrow = AsyncMock(side_effect=[None, new_row])

        provisioner = JITProvisioner(db_pool=pool)
        user = _make_user()
        result = await provisioner.provision(user)

        assert result["sso_provider"] == "keycloak"
        assert result["email"] == "user@corp.com"
        # Verify INSERT SQL includes sso_provider
        insert_call = conn.fetchrow.call_args_list[1]
        sql = insert_call[0][0]
        assert "sso_provider" in sql

    @pytest.mark.asyncio
    async def test_existing_user_updated_with_provider_where(self) -> None:
        """UPDATE WHERE clause should filter by sso_provider AND sso_sub."""
        existing = {
            "id": 1, "sso_provider": "keycloak", "sso_sub": "uid-sso-123",
            "email": "user@corp.com", "display_name": "Old Name",
            "department": "Old Dept", "role": "user",
        }
        pool, conn = _make_pool_mock()
        conn.fetchrow = AsyncMock(return_value=existing)

        provisioner = JITProvisioner(db_pool=pool)
        user = _make_user(name="New Name", department="New Dept")
        result = await provisioner.provision(user)

        # Should return existing record with mapped role
        assert result["id"] == 1
        # Verify UPDATE SQL uses sso_provider
        update_call = conn.execute.call_args
        sql = update_call[0][0]
        assert "sso_provider" in sql

    @pytest.mark.asyncio
    async def test_different_providers_same_sub_are_distinct(self) -> None:
        """Same sub from different providers should be treated as different users."""
        pool, conn = _make_pool_mock()
        # keycloak user not found → insert
        new_row = {"id": 2, "sso_provider": "dingtalk", "sso_sub": "shared-sub"}
        conn.fetchrow = AsyncMock(side_effect=[None, new_row])

        provisioner = JITProvisioner(db_pool=pool)
        user = _make_user(sub="shared-sub", provider="dingtalk")
        result = await provisioner.provision(user)

        # SELECT should have used both provider and sub
        select_call = conn.fetchrow.call_args_list[0]
        sql = select_call[0][0]
        assert "sso_provider" in sql
        assert "sso_sub" in sql

    @pytest.mark.asyncio
    async def test_pg_none_uses_memory_fallback(self) -> None:
        """When db_pool is None, falls back to in-memory (for testing only)."""
        provisioner = JITProvisioner(db_pool=None)
        user = _make_user()
        result = await provisioner.provision(user)
        assert result["sso_sub"] == "uid-sso-123"
        assert result["role"] == "viewer"

    @pytest.mark.asyncio
    async def test_pg_error_propagates_not_silent(self) -> None:
        """PG errors should propagate, not silently fall back to memory."""
        pool, conn = _make_pool_mock()
        conn.fetchrow = AsyncMock(side_effect=Exception("connection refused"))

        provisioner = JITProvisioner(db_pool=pool)
        user = _make_user()
        with pytest.raises(Exception, match="connection refused"):
            await provisioner.provision(user)
