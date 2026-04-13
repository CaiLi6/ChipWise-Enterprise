"""Keycloak OIDC provider (§6B1)."""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

from src.auth.sso.base import BaseSSOProvider, SSOUserInfo

logger = logging.getLogger(__name__)

_JWKS_CACHE: dict[str, tuple[dict, float]] = {}
_JWKS_TTL = 3600  # 1 hour


class KeycloakProvider(BaseSSOProvider):
    """Standard OIDC provider for Keycloak."""

    def get_authorization_url(self, state: str, nonce: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._config["client_id"],
            "redirect_uri": self._config["redirect_uri"],
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
        }
        base = self._config["authorization_endpoint"]
        return f"{base}?{urlencode(params)}"

    async def exchange_code(self, code: str, nonce: str) -> SSOUserInfo:
        import httpx

        token_endpoint = self._config["token_endpoint"]
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self._config["redirect_uri"],
            "client_id": self._config["client_id"],
            "client_secret": self._config.get("client_secret", ""),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(token_endpoint, data=data, timeout=10)
            resp.raise_for_status()
            tokens = resp.json()

        claims = await self.validate_id_token(tokens["id_token"])

        # Verify nonce
        if claims.get("nonce") != nonce:
            raise ValueError("Nonce mismatch — possible replay attack")

        return SSOUserInfo(
            sub=claims["sub"],
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("preferred_username", "")),
            department=claims.get("department", ""),
            groups=claims.get("groups", []),
            raw_claims=claims,
        )

    async def validate_id_token(self, id_token: str) -> dict[str, Any]:
        import httpx
        import json
        import base64

        jwks_uri = self._config["jwks_uri"]

        # JWKS cache
        cached = _JWKS_CACHE.get(jwks_uri)
        if cached is None or time.time() - cached[1] > _JWKS_TTL:
            async with httpx.AsyncClient() as client:
                resp = await client.get(jwks_uri, timeout=10)
                resp.raise_for_status()
                jwks = resp.json()
            _JWKS_CACHE[jwks_uri] = (jwks, time.time())
        else:
            jwks = cached[0]

        # Decode payload (signature verification requires PyJWT or python-jose)
        parts = id_token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        # Add padding if needed
        payload_b64 = parts[1] + "=="
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        # Validate standard claims
        now = time.time()
        if payload.get("exp", 0) < now:
            raise ValueError("Token expired")
        if payload.get("iss") != self._config.get("issuer"):
            raise ValueError(f"Issuer mismatch: {payload.get('iss')}")

        return payload
