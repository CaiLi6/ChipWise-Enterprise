"""JIT (Just-In-Time) user provisioning on first SSO login (§6B2)."""

from __future__ import annotations

import logging
from typing import Any

from src.auth.sso.base import SSOUserInfo

logger = logging.getLogger(__name__)

# Role mapping: IdP group → internal role
_GROUP_ROLE_MAP = {
    "chipwise-admin": "admin",
    "chipwise-engineers": "user",
    "chipwise-viewers": "viewer",
}


class JITProvisioner:
    """Create or update local users on first SSO login."""

    def __init__(self, db_pool: Any = None) -> None:
        self._pool = db_pool
        # In-memory fallback for testing
        self._users: dict[str, dict[str, Any]] = {}

    async def provision(self, sso_user: SSOUserInfo) -> dict[str, Any]:
        """Create a new user or update existing one from SSO info.

        Args:
            sso_user: Normalized user info from IdP.

        Returns:
            User dict with id, username, email, role.
        """
        role = self._map_role(sso_user.groups)

        if self._pool:
            return await self._provision_pg(sso_user, role)
        return self._provision_memory(sso_user, role)

    def _map_role(self, groups: list[str]) -> str:
        """Map IdP groups to internal role. Returns highest-priority role."""
        _priority = {"admin": 2, "user": 1, "viewer": 0}
        best = "viewer"
        for group in groups:
            role = _GROUP_ROLE_MAP.get(group)
            if role and _priority.get(role, -1) > _priority.get(best, -1):
                best = role
        return best

    async def _provision_pg(self, sso_user: SSOUserInfo, role: str) -> dict[str, Any]:
        """Write user to PostgreSQL."""
        async with self._pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT * FROM users WHERE sso_provider = $1 AND sso_sub = $2",
                sso_user.provider, sso_user.sub,
            )
            if existing:
                await conn.execute(
                    "UPDATE users SET display_name=$1, department=$2, last_login_at=NOW() "
                    "WHERE sso_provider=$3 AND sso_sub=$4",
                    sso_user.name, sso_user.department, sso_user.provider, sso_user.sub,
                )
                return dict(existing) | {"role": role}
            else:
                row = await conn.fetchrow(
                    """INSERT INTO users
                       (sso_provider, sso_sub, email, display_name, department, role, last_login_at)
                       VALUES ($1, $2, $3, $4, $5, $6, NOW()) RETURNING *""",
                    sso_user.provider, sso_user.sub, sso_user.email,
                    sso_user.name, sso_user.department, role,
                )
                return dict(row)

    def _provision_memory(self, sso_user: SSOUserInfo, role: str) -> dict[str, Any]:
        """In-memory fallback (testing / no-DB mode)."""
        if sso_user.sub in self._users:
            self._users[sso_user.sub].update(
                display_name=sso_user.name, department=sso_user.department
            )
        else:
            self._users[sso_user.sub] = {
                "id": len(self._users) + 1,
                "sso_sub": sso_user.sub,
                "email": sso_user.email,
                "display_name": sso_user.name,
                "department": sso_user.department,
                "role": role,
            }
        return self._users[sso_user.sub]
