"""SSO/OIDC authentication router — login redirect and callback (§6B1)."""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from src.api.dependencies import get_settings
from src.auth.sso.jit_provisioning import JITProvisioner

logger = logging.getLogger("chipwise.sso")

router = APIRouter(prefix="/api/v1/auth/sso", tags=["sso"])

# In-memory CSRF state store: state_token -> {nonce, provider, expires_at}
# In production this should be Redis with TTL.
_STATE_STORE: dict[str, dict[str, Any]] = {}
_STATE_TTL = 600  # 10 minutes


def _build_provider(provider_name: str, settings: Any) -> Any:
    """Construct the appropriate SSO provider from settings."""
    sso = settings.auth.sso

    if provider_name == "keycloak":
        from src.auth.sso.keycloak import KeycloakProvider
        config: dict[str, Any] = {
            "client_id": sso.client_id,
            "client_secret": sso.client_secret,
            "redirect_uri": sso.redirect_uri,
            "issuer": sso.issuer,
            # Standard Keycloak OIDC endpoint derivation
            "authorization_endpoint": f"{sso.issuer}/protocol/openid-connect/auth",
            "token_endpoint": f"{sso.issuer}/protocol/openid-connect/token",
            "jwks_uri": f"{sso.issuer}/protocol/openid-connect/certs",
        }
        return KeycloakProvider(config)

    if provider_name == "dingtalk":
        from src.auth.sso.dingtalk import DingTalkProvider
        config = {
            "client_id": sso.client_id,
            "client_secret": sso.client_secret,
            "redirect_uri": sso.redirect_uri,
        }
        return DingTalkProvider(config)

    if provider_name == "feishu":
        from src.auth.sso.feishu import FeishuProvider
        config = {
            "client_id": sso.client_id,
            "client_secret": sso.client_secret,
            "redirect_uri": sso.redirect_uri,
        }
        return FeishuProvider(config)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Unknown SSO provider '{provider_name}'. "
            "Supported: keycloak, dingtalk, feishu"
        ),
    )


@router.get("/login")
async def sso_login(provider: str = "keycloak") -> RedirectResponse:
    """Initiate SSO login: redirect the user's browser to the identity provider.

    Query params:
        provider: keycloak | dingtalk | feishu  (default: keycloak)

    Returns:
        302 redirect to IdP authorization URL.
    """
    settings = get_settings()

    if not settings.auth.sso.client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"SSO not configured for provider '{provider}' "
                "(auth.sso.client_id is empty in settings)"
            ),
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    _STATE_STORE[state] = {
        "nonce": nonce,
        "provider": provider,
        "expires_at": time.time() + _STATE_TTL,
    }

    sso_provider = _build_provider(provider, settings)
    authorization_url = sso_provider.get_authorization_url(state=state, nonce=nonce)
    logger.info("SSO login redirect: provider=%s", provider)
    return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def sso_callback(
    code: str,
    state: str,
    request: Request,
) -> dict[str, Any]:
    """Handle IdP authorization callback.

    Exchanges the code for tokens, JIT-provisions the user, and returns
    ChipWise JWT tokens.

    Query params:
        code:  Authorization code from IdP.
        state: CSRF state token (must match the value sent in /login).

    Returns:
        JSON with access_token, refresh_token, token_type, expires_in, user.
    """
    # --- CSRF state validation ---
    stored = _STATE_STORE.pop(state, None)
    if stored is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state parameter — possible CSRF attempt",
        )
    if time.time() > stored["expires_at"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State parameter expired — restart the login flow",
        )

    settings = get_settings()
    provider_name: str = stored["provider"]
    nonce: str = stored["nonce"]

    sso_provider = _build_provider(provider_name, settings)

    # --- Token exchange ---
    try:
        user_info = await sso_provider.exchange_code(code=code, nonce=nonce)
    except Exception as exc:
        logger.error("SSO token exchange failed (provider=%s): %s", provider_name, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"SSO provider error: {exc}",
        ) from exc

    # --- JIT provision ---
    provisioner = JITProvisioner(db_pool=None)  # In-memory fallback; wired to PG in prod
    user = await provisioner.provision(user_info)

    # --- Issue ChipWise JWT ---
    from src.api.middleware.auth import create_access_token, create_refresh_token

    payload: dict[str, Any] = {
        "sub": user_info.sub,
        "username": user.get("display_name", user_info.email),
        "role": user.get("role", "viewer"),
        "department": user_info.department,
    }
    access_token = create_access_token(payload, settings.auth)
    refresh_token = create_refresh_token(payload, settings.auth)

    logger.info(
        "SSO login successful: provider=%s email=%s role=%s",
        provider_name,
        user_info.email,
        user.get("role"),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.auth.jwt.access_token_expire_minutes * 60,
        "user": {
            "email": user_info.email,
            "name": user_info.name,
            "role": user.get("role", "viewer"),
        },
    }
