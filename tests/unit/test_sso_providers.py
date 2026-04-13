"""Unit tests for SSO providers (§6B1)."""

from __future__ import annotations

import pytest

from src.auth.sso.base import BaseSSOProvider, SSOUserInfo
from src.auth.sso.factory import SSOProviderFactory
from src.auth.sso.keycloak import KeycloakProvider
from src.auth.sso.dingtalk import DingTalkProvider
from src.auth.sso.feishu import FeishuProvider


_KEYCLOAK_CONFIG = {
    "client_id": "chipwise",
    "client_secret": "secret",
    "redirect_uri": "http://localhost:8080/api/v1/auth/sso/callback",
    "authorization_endpoint": "https://sso.example.com/auth/realms/chipwise/protocol/openid-connect/auth",
    "token_endpoint": "https://sso.example.com/auth/realms/chipwise/protocol/openid-connect/token",
    "jwks_uri": "https://sso.example.com/auth/realms/chipwise/protocol/openid-connect/certs",
    "issuer": "https://sso.example.com/auth/realms/chipwise",
}

_DINGTALK_CONFIG = {
    "client_id": "ding_app_id",
    "client_secret": "ding_secret",
    "redirect_uri": "http://localhost:8080/callback",
}

_FEISHU_CONFIG = {
    "client_id": "feishu_app_id",
    "client_secret": "feishu_secret",
    "redirect_uri": "http://localhost:8080/callback",
}


@pytest.mark.unit
class TestSSOProviderFactory:
    def test_create_keycloak_provider(self) -> None:
        provider = SSOProviderFactory.create("keycloak", _KEYCLOAK_CONFIG)
        assert isinstance(provider, KeycloakProvider)

    def test_create_dingtalk_provider(self) -> None:
        provider = SSOProviderFactory.create("dingtalk", _DINGTALK_CONFIG)
        assert isinstance(provider, DingTalkProvider)

    def test_create_feishu_provider(self) -> None:
        provider = SSOProviderFactory.create("feishu", _FEISHU_CONFIG)
        assert isinstance(provider, FeishuProvider)

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown SSO provider"):
            SSOProviderFactory.create("okta", {})

    def test_factory_registry_contains_known_providers(self) -> None:
        for name in ("keycloak", "dingtalk", "feishu"):
            assert name in SSOProviderFactory._registry


@pytest.mark.unit
class TestKeycloakProvider:
    @pytest.fixture
    def provider(self) -> KeycloakProvider:
        return KeycloakProvider(_KEYCLOAK_CONFIG)

    def test_get_authorization_url_contains_client_id(self, provider: KeycloakProvider) -> None:
        url = provider.get_authorization_url(state="abc123", nonce="nonce456")
        assert "client_id=chipwise" in url
        assert "response_type=code" in url
        assert "openid" in url

    def test_get_authorization_url_contains_nonce(self, provider: KeycloakProvider) -> None:
        url = provider.get_authorization_url(state="s", nonce="my_nonce")
        assert "nonce=my_nonce" in url

    def test_get_authorization_url_contains_state(self, provider: KeycloakProvider) -> None:
        url = provider.get_authorization_url(state="my_state", nonce="n")
        assert "state=my_state" in url

    def test_get_authorization_url_base(self, provider: KeycloakProvider) -> None:
        url = provider.get_authorization_url(state="s", nonce="n")
        assert url.startswith(_KEYCLOAK_CONFIG["authorization_endpoint"])


@pytest.mark.unit
class TestDingTalkProvider:
    @pytest.fixture
    def provider(self) -> DingTalkProvider:
        return DingTalkProvider(_DINGTALK_CONFIG)

    def test_get_authorization_url_contains_app_id(self, provider: DingTalkProvider) -> None:
        url = provider.get_authorization_url(state="s", nonce="n")
        assert "ding_app_id" in url

    def test_get_authorization_url_contains_state(self, provider: DingTalkProvider) -> None:
        url = provider.get_authorization_url(state="xyz", nonce="n")
        assert "xyz" in url

    def test_is_base_sso_provider(self, provider: DingTalkProvider) -> None:
        assert isinstance(provider, BaseSSOProvider)


@pytest.mark.unit
class TestFeishuProvider:
    @pytest.fixture
    def provider(self) -> FeishuProvider:
        return FeishuProvider(_FEISHU_CONFIG)

    def test_get_authorization_url_contains_app_id(self, provider: FeishuProvider) -> None:
        url = provider.get_authorization_url(state="s", nonce="n")
        assert "feishu_app_id" in url

    def test_is_base_sso_provider(self, provider: FeishuProvider) -> None:
        assert isinstance(provider, BaseSSOProvider)


@pytest.mark.unit
class TestSSOUserInfo:
    def test_sso_user_info_defaults(self) -> None:
        user = SSOUserInfo(sub="u1", email="u@e.com", name="User One")
        assert user.department == ""
        assert user.groups == []
        assert user.avatar_url == ""
        assert user.raw_claims == {}

    def test_sso_user_info_full(self) -> None:
        user = SSOUserInfo(
            sub="u1", email="u@e.com", name="User One",
            department="Engineering", groups=["chipwise-admin"],
            raw_claims={"iss": "https://sso.example.com"},
        )
        assert user.department == "Engineering"
        assert "chipwise-admin" in user.groups
