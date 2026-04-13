"""DingTalk OAuth2 provider (§6B1)."""

from __future__ import annotations

from urllib.parse import urlencode

from src.auth.sso.base import BaseSSOProvider, SSOUserInfo


class DingTalkProvider(BaseSSOProvider):
    """DingTalk enterprise internal app OAuth2."""

    _AUTH_URL = "https://login.dingtalk.com/oauth2/auth"
    _TOKEN_URL = "https://api.dingtalk.com/v1.0/oauth2/userAccessToken"
    _USERINFO_URL = "https://api.dingtalk.com/v1.0/contact/users/me"

    def get_authorization_url(self, state: str, nonce: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self._config["client_id"],
            "redirect_uri": self._config["redirect_uri"],
            "scope": "openid",
            "state": state,
            "prompt": "consent",
        }
        return f"{self._AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, nonce: str) -> SSOUserInfo:
        import httpx

        async with httpx.AsyncClient() as client:
            # Exchange code for access token
            token_resp = await client.post(
                self._TOKEN_URL,
                json={
                    "clientId": self._config["client_id"],
                    "clientSecret": self._config["client_secret"],
                    "code": code,
                    "grantType": "authorization_code",
                },
                timeout=10,
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()
            access_token = tokens["accessToken"]

            # Get user info
            user_resp = await client.get(
                self._USERINFO_URL,
                headers={"x-acs-dingtalk-access-token": access_token},
                timeout=10,
            )
            user_resp.raise_for_status()
            user = user_resp.json()

        return SSOUserInfo(
            sub=user.get("unionId", user.get("openId", "")),
            email=user.get("email", ""),
            name=user.get("nick", ""),
            department=user.get("title", ""),
            groups=[],
            raw_claims=user,
        )
