"""Unit tests for JIT user provisioning (§6B2)."""

from __future__ import annotations

import pytest

from src.auth.sso.base import SSOUserInfo
from src.auth.sso.jit_provisioning import JITProvisioner


def _make_user(
    sub: str = "uid123",
    email: str = "u@example.com",
    name: str = "Test User",
    groups: list[str] | None = None,
) -> SSOUserInfo:
    return SSOUserInfo(sub=sub, email=email, name=name, groups=groups or [])


@pytest.mark.unit
class TestJITProvisionerRoleMapping:
    def test_admin_group_maps_to_admin(self) -> None:
        provisioner = JITProvisioner()
        role = provisioner._map_role(["chipwise-admin"])
        assert role == "admin"

    def test_engineers_group_maps_to_user(self) -> None:
        provisioner = JITProvisioner()
        role = provisioner._map_role(["chipwise-engineers"])
        assert role == "user"

    def test_viewers_group_maps_to_viewer(self) -> None:
        provisioner = JITProvisioner()
        role = provisioner._map_role(["chipwise-viewers"])
        assert role == "viewer"

    def test_no_group_defaults_to_viewer(self) -> None:
        provisioner = JITProvisioner()
        role = provisioner._map_role([])
        assert role == "viewer"

    def test_unknown_group_defaults_to_viewer(self) -> None:
        provisioner = JITProvisioner()
        role = provisioner._map_role(["some-other-group"])
        assert role == "viewer"

    def test_admin_takes_priority(self) -> None:
        provisioner = JITProvisioner()
        role = provisioner._map_role(["chipwise-engineers", "chipwise-admin"])
        assert role == "admin"


@pytest.mark.unit
class TestJITProvisionerMemory:
    @pytest.mark.asyncio
    async def test_new_user_created(self) -> None:
        provisioner = JITProvisioner()
        user = _make_user(sub="new1", groups=["chipwise-engineers"])

        result = await provisioner.provision(user)

        assert result["sso_sub"] == "new1"
        assert result["email"] == "u@example.com"
        assert result["role"] == "user"

    @pytest.mark.asyncio
    async def test_existing_user_updated(self) -> None:
        provisioner = JITProvisioner()

        user = _make_user(sub="existing1", name="Old Name")
        await provisioner.provision(user)

        updated_user = _make_user(sub="existing1", name="New Name")
        result = await provisioner.provision(updated_user)

        assert result["display_name"] == "New Name"

    @pytest.mark.asyncio
    async def test_two_users_tracked_separately(self) -> None:
        provisioner = JITProvisioner()

        u1 = _make_user(sub="user_a", name="Alice", groups=["chipwise-admin"])
        u2 = _make_user(sub="user_b", name="Bob", groups=["chipwise-viewers"])

        r1 = await provisioner.provision(u1)
        r2 = await provisioner.provision(u2)

        assert r1["role"] == "admin"
        assert r2["role"] == "viewer"
        assert r1["sso_sub"] != r2["sso_sub"]

    @pytest.mark.asyncio
    async def test_provision_returns_user_dict(self) -> None:
        provisioner = JITProvisioner()
        user = _make_user()
        result = await provisioner.provision(user)

        assert isinstance(result, dict)
        assert "sso_sub" in result
        assert "email" in result
        assert "role" in result
