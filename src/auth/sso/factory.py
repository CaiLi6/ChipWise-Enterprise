"""SSOProviderFactory (§6B1)."""

from __future__ import annotations

from typing import Any

from src.auth.sso.base import BaseSSOProvider


class SSOProviderFactory:
    """Create SSO provider instances by name."""

    _registry: dict[str, type[BaseSSOProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[BaseSSOProvider]) -> None:
        cls._registry[name] = provider_class

    @classmethod
    def create(cls, provider_name: str, config: dict[str, Any]) -> BaseSSOProvider:
        if provider_name not in cls._registry:
            raise ValueError(
                f"Unknown SSO provider: '{provider_name}'. "
                f"Available: {sorted(cls._registry)}"
            )
        return cls._registry[provider_name](config)


# Auto-register known providers
def _auto_register() -> None:
    from src.auth.sso.dingtalk import DingTalkProvider
    from src.auth.sso.feishu import FeishuProvider
    from src.auth.sso.keycloak import KeycloakProvider

    SSOProviderFactory.register("keycloak", KeycloakProvider)
    SSOProviderFactory.register("dingtalk", DingTalkProvider)
    SSOProviderFactory.register("feishu", FeishuProvider)


_auto_register()
