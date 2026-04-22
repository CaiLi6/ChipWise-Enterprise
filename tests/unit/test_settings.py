"""Tests for Settings loader, validation, and environment overrides."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.core.settings import Settings, load_settings

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.mark.unit
class TestLoadSettings:
    """load_settings() happy-path tests."""

    def test_load_valid_yaml(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert isinstance(settings, Settings)

    def test_llm_primary_accessible(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.llm.primary.base_url == "http://localhost:1234/v1"
        assert settings.llm.primary.model == "qwen3-35b-q5_k_m"

    def test_llm_router_accessible(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.llm.router.model == "qwen3-1.7b-q5_k_m"

    def test_database_accessible(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.database.host == "localhost"
        assert settings.database.port == 5432

    def test_redis_accessible(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.redis.host == "localhost"

    def test_vector_store_backend(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.vector_store.backend == "milvus"

    def test_agent_settings(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.agent.max_iterations == 5
        assert settings.agent.max_total_tokens == 8192

    def test_graph_store_settings(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.graph_store.backend == "kuzu"
        assert settings.graph_store.kuzu.db_path == "data/kuzu"

    def test_auth_sso_accessible(self) -> None:
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.auth.sso.provider == "keycloak"


@pytest.mark.unit
class TestValidation:
    """Validation and error paths."""

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_settings("/nonexistent/path.yaml")

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(ValueError, match="llm.primary.model"):
            load_settings(str(FIXTURES / "settings_missing_field.yaml"))


@pytest.mark.unit
class TestEnvOverrides:
    """Environment variable overrides."""

    def test_pg_password_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PG_PASSWORD", "secret-from-env")
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.database.password == "secret-from-env"

    def test_redis_password_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("REDIS_PASSWORD", "redis-secret")
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.redis.password == "redis-secret"

    def test_jwt_secret_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET_KEY", "jwt-from-env")
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.auth.local_fallback.jwt_secret == "jwt-from-env"

    def test_sso_client_secret_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SSO_CLIENT_SECRET", "sso-from-env")
        settings = load_settings(str(FIXTURES / "settings_valid.yaml"))
        assert settings.auth.sso.client_secret == "sso-from-env"


@pytest.mark.unit
class TestProjectSettingsYaml:
    """Verify the actual project config/settings.yaml loads correctly."""

    def test_load_project_settings(self) -> None:
        settings = load_settings("config/settings.yaml")
        assert isinstance(settings, Settings)
        # Both LM Studio model slugs are defined and non-empty.
        assert settings.llm.primary.model
        assert settings.llm.router.model
        assert settings.llm.primary.base_url.endswith(":1234/v1")
