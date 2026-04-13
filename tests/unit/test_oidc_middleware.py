"""Unit tests for OIDC auth middleware (§6B2)."""

from __future__ import annotations

import base64
import json
import time

import pytest
from unittest.mock import AsyncMock, patch

from src.api.middleware.oidc_auth import OIDCAuthMiddleware


def _make_jwt(payload: dict, header: dict | None = None) -> str:
    """Build a minimal JWT string (unsigned, for testing claim validation)."""
    h = header or {"alg": "RS256", "typ": "JWT"}
    h_b64 = base64.urlsafe_b64encode(json.dumps(h).encode()).rstrip(b"=").decode()
    p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{h_b64}.{p_b64}.fakesig"


_CONFIG = {
    "issuer": "https://sso.example.com/realms/chipwise",
    "audience": "chipwise",
    "openid_config_url": "https://sso.example.com/realms/chipwise/.well-known/openid-configuration",
}


@pytest.fixture
def middleware() -> OIDCAuthMiddleware:
    return OIDCAuthMiddleware(_CONFIG)


@pytest.mark.unit
class TestVerifyToken:
    @pytest.mark.asyncio
    async def test_valid_token_returns_payload(self, middleware: OIDCAuthMiddleware) -> None:
        payload = {
            "sub": "user123",
            "iss": _CONFIG["issuer"],
            "aud": _CONFIG["audience"],
            "exp": int(time.time()) + 3600,
        }
        token = _make_jwt(payload)

        with patch.object(middleware, "get_jwks", new=AsyncMock(return_value={})):
            result = await middleware.verify_token(token)

        assert result["sub"] == "user123"

    @pytest.mark.asyncio
    async def test_expired_token_raises(self, middleware: OIDCAuthMiddleware) -> None:
        payload = {
            "sub": "u1",
            "iss": _CONFIG["issuer"],
            "aud": _CONFIG["audience"],
            "exp": int(time.time()) - 10,  # Already expired
        }
        token = _make_jwt(payload)

        with patch.object(middleware, "get_jwks", new=AsyncMock(return_value={})):
            with pytest.raises(ValueError, match="expired"):
                await middleware.verify_token(token)

    @pytest.mark.asyncio
    async def test_wrong_issuer_raises(self, middleware: OIDCAuthMiddleware) -> None:
        payload = {
            "sub": "u1",
            "iss": "https://evil.com",
            "aud": _CONFIG["audience"],
            "exp": int(time.time()) + 3600,
        }
        token = _make_jwt(payload)

        with patch.object(middleware, "get_jwks", new=AsyncMock(return_value={})):
            with pytest.raises(ValueError, match="Issuer"):
                await middleware.verify_token(token)

    @pytest.mark.asyncio
    async def test_wrong_audience_raises(self, middleware: OIDCAuthMiddleware) -> None:
        payload = {
            "sub": "u1",
            "iss": _CONFIG["issuer"],
            "aud": "other-app",
            "exp": int(time.time()) + 3600,
        }
        token = _make_jwt(payload)

        with patch.object(middleware, "get_jwks", new=AsyncMock(return_value={})):
            with pytest.raises(ValueError, match="Audience"):
                await middleware.verify_token(token)

    @pytest.mark.asyncio
    async def test_malformed_jwt_raises(self, middleware: OIDCAuthMiddleware) -> None:
        with pytest.raises(ValueError, match="Malformed"):
            await middleware.verify_token("not.a.jwt.token.parts")

    @pytest.mark.asyncio
    async def test_jwks_failure_does_not_block_claim_validation(self, middleware: OIDCAuthMiddleware) -> None:
        """JWKS fetch failure should warn but not block claim validation."""
        payload = {
            "sub": "u1",
            "iss": _CONFIG["issuer"],
            "aud": _CONFIG["audience"],
            "exp": int(time.time()) + 3600,
        }
        token = _make_jwt(payload)

        with patch.object(middleware, "get_jwks", new=AsyncMock(side_effect=Exception("Network error"))):
            result = await middleware.verify_token(token)

        assert result["sub"] == "u1"


@pytest.mark.unit
class TestJWKSCache:
    @pytest.mark.asyncio
    async def test_jwks_cached_after_first_fetch(self, middleware: OIDCAuthMiddleware) -> None:
        from src.api.middleware.oidc_auth import _JWKS_CACHE
        from unittest.mock import MagicMock

        jwks_data = {"keys": [{"kid": "key1", "kty": "RSA"}]}
        discovery = {"jwks_uri": "https://sso.example.com/jwks"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)

            # httpx Response.json() and .raise_for_status() are synchronous
            disc_resp = MagicMock()
            disc_resp.json.return_value = discovery
            disc_resp.raise_for_status = MagicMock()

            jwks_resp = MagicMock()
            jwks_resp.json.return_value = jwks_data
            jwks_resp.raise_for_status = MagicMock()

            mock_client.get = AsyncMock(side_effect=[disc_resp, jwks_resp])

            await middleware.get_jwks()

        # Cache should be populated
        config_url = _CONFIG["openid_config_url"]
        assert config_url in _JWKS_CACHE
