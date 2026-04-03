"""Tests for build_info module."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from colette.build_info import BuildInfo, _resolve_environment, get_build_info


class TestBuildInfo:
    def test_version_display_clean(self) -> None:
        info = BuildInfo(
            version="0.2.0",
            git_sha_short="abc1234",
            git_branch="main",
            build_date="2026-04-03T12:00:00Z",
        )
        assert info.version_display == "0.2.0 (abc1234, main, 2026-04-03T12:00:00Z)"

    def test_version_display_dirty(self) -> None:
        info = BuildInfo(
            version="0.2.0",
            git_sha_short="abc1234",
            git_branch="feat/x",
            git_dirty=True,
            build_date="2026-04-03T12:00:00Z",
        )
        assert info.version_display.startswith("0.2.0+dirty")
        assert "abc1234" in info.version_display

    def test_version_display_no_git(self) -> None:
        info = BuildInfo(version="0.2.0", build_date="2026-04-03T12:00:00Z")
        assert info.version_display == "0.2.0 (2026-04-03T12:00:00Z)"

    def test_to_dict_structure(self) -> None:
        info = BuildInfo(
            version="1.0.0",
            git_sha="abc123full",
            git_sha_short="abc1234",
            git_branch="main",
            python_version="3.13.0",
            platform_system="Linux",
            platform_machine="x86_64",
            environment="production",
        )
        d = info.to_dict()
        assert d["version"] == "1.0.0"
        assert d["git"]["sha"] == "abc123full"
        assert d["git"]["sha_short"] == "abc1234"
        assert d["git"]["branch"] == "main"
        assert d["python"] == "3.13.0"
        assert d["platform"] == "Linux/x86_64"
        assert d["environment"] == "production"

    def test_frozen(self) -> None:
        info = BuildInfo(version="0.1.0")
        with pytest.raises(AttributeError):
            info.version = "changed"  # type: ignore[misc]


class TestResolveEnvironment:
    def test_explicit_env_var(self) -> None:
        with patch.dict("os.environ", {"COLETTE_ENVIRONMENT": "production"}):
            assert _resolve_environment() == "production"

    def test_staging(self) -> None:
        with patch.dict("os.environ", {"COLETTE_ENVIRONMENT": "staging"}):
            assert _resolve_environment() == "staging"

    def test_ci_detection(self) -> None:
        with patch.dict("os.environ", {"CI": "true"}, clear=False):
            env = {"CI": "true"}
            with patch.dict("os.environ", env, clear=True):
                assert _resolve_environment() == "testing"

    def test_k8s_detection(self) -> None:
        env = {"KUBERNETES_SERVICE_HOST": "10.0.0.1"}
        with patch.dict("os.environ", env, clear=True):
            assert _resolve_environment() == "production"

    def test_default_development(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            assert _resolve_environment() == "development"


class TestGetBuildInfo:
    def test_returns_build_info(self) -> None:
        info = get_build_info()
        assert isinstance(info, BuildInfo)
        assert info.version != ""
        assert re.match(r"^\d+\.\d+\.\d+", info.version)
        assert info.python_version != ""
        assert info.platform_system != ""

    def test_git_sha_populated_in_repo(self) -> None:
        """Should have git info when running in the colette repo."""
        info = get_build_info()
        # We're running tests inside the repo, so git info should be available
        assert info.git_sha_short != ""
        assert len(info.git_sha_short) >= 7
        assert info.git_branch != ""
