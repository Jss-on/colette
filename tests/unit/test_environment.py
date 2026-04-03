"""Tests for environment configuration."""

from __future__ import annotations

from unittest.mock import patch

from colette.config import Environment, Settings


class TestEnvironmentEnum:
    def test_values(self) -> None:
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"
        assert Environment.TESTING.value == "testing"

    def test_is_production(self) -> None:
        assert Environment.PRODUCTION.is_production is True
        assert Environment.STAGING.is_production is False
        assert Environment.DEVELOPMENT.is_production is False

    def test_is_development(self) -> None:
        assert Environment.DEVELOPMENT.is_development is True
        assert Environment.TESTING.is_development is True
        assert Environment.PRODUCTION.is_development is False
        assert Environment.STAGING.is_development is False


class TestProductionDefaults:
    def test_prod_disables_debug(self) -> None:
        with patch.dict(
            "os.environ",
            {"COLETTE_ENVIRONMENT": "production", "COLETTE_DEBUG": "true"},
            clear=False,
        ):
            s = Settings()
            assert s.debug is False

    def test_prod_clears_wildcard_cors(self) -> None:
        with patch.dict(
            "os.environ",
            {"COLETTE_ENVIRONMENT": "production"},
            clear=False,
        ):
            s = Settings()
            assert s.cors_origins == []

    def test_prod_uses_postgres_checkpoint(self) -> None:
        with patch.dict(
            "os.environ",
            {"COLETTE_ENVIRONMENT": "production"},
            clear=False,
        ):
            s = Settings()
            assert s.checkpoint_backend == "postgres"

    def test_dev_keeps_defaults(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "COLETTE_ENVIRONMENT": "development",
                "COLETTE_CHECKPOINT_BACKEND": "memory",
                "COLETTE_CORS_ORIGINS": '["*"]',
            },
            clear=False,
        ):
            s = Settings()
            assert s.cors_origins == ["*"]
            assert s.checkpoint_backend == "memory"

    def test_default_environment_is_development(self) -> None:
        s = Settings()
        assert s.environment == Environment.DEVELOPMENT
