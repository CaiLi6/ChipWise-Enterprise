"""Feishu (Lark) OAuth2 provider (§6B1)."""

from __future__ import annotations

from urllib.parse import urlencode

from src.auth.sso.base import BaseSSOProvider, SSOUserInfo


class FeishuProvider(BaseSSOProvider):
    """Feishu self-built app OAuth2."""

    _AUTH_URL = "https://accounts.feishu.cn/open-apis/authen/v1/index"
    _TOKEN_URL = "https://open.feishu.cn/open-apis/authen/v1/access_token"
    _USERINFO_URL = "https://open.feishu.cn/open-apis/authen/v1/user_info"

    def get_authorization_url(self, state: str, nonce: str) -> str:
        params = {
            "app_id": self._config["client_id"],
            "redirect_uri": self._config["redirect_uri"],
            "state": state,
        }
        return f"{self._AUTH_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, nonce: str) -> SSOUserInfo:
        import httpx

        async with httpx.AsyncClient() as client:
            # Get app access token first
            app_token_resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
                json={
                    "app_id": self._config["client_id"],
                    "app_secret": self._config["client_secret"],
                },
                timeout=10,
            )
            app_token_resp.raise_for_status()
            app_token = app_token_resp.json()["app_access_token"]

            # Exchange code for user access token
            token_resp = await client.post(
                self._TOKEN_URL,
                json={"grant_type": "authorization_code", "code": code},
                headers={"Authorization": f"Bearer {app_token}"},
                timeout=10,
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()["data"]
            user_token = token_data["access_token"]

            # Get user info
            user_resp = await client.get(
                self._USERINFO_URL,
                headers={"Authorization": f"Bearer {user_token}"},
                timeout=10,
            )
            user_resp.raise_for_status()
            user = user_resp.json()["data"]

        return SSOUserInfo(
            sub=user.get("open_id", user.get("union_id", "")),
            email=user.get("email", user.get("enterprise_email", "")),
            name=user.get("name", ""),
            department=user.get("job_title", ""),
            groups=user.get("department_ids", []),
            raw_claims=user,
        )
