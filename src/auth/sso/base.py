"""BaseSSOProvider and SSOUserInfo (§6B1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSOUserInfo:
    """Normalized user identity from any SSO provider."""

    sub: str
    email: str
    name: str
    provider: str = ""
    department: str = ""
    groups: list[str] = field(default_factory=list)
    avatar_url: str = ""
    raw_claims: dict[str, Any] = field(default_factory=dict)


class BaseSSOProvider(ABC):
    """Abstract base for SSO / OAuth2 identity providers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config

    @abstractmethod
    def get_authorization_url(self, state: str, nonce: str) -> str:
        """Build the IdP redirect URL for the authorization code flow."""

    @abstractmethod
    async def exchange_code(self, code: str, nonce: str) -> SSOUserInfo:
        """Exchange authorization code for tokens and return user info."""

    async def validate_id_token(self, id_token: str) -> dict[str, Any]:
        """Validate an id_token using JWKS.  Override for OIDC providers."""
        raise NotImplementedError("validate_id_token not implemented for this provider")
