"""Tests for CLI commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from colette.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_version(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "colette" in result.output


def test_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "submit" in result.output
    assert "status" in result.output
    assert "approve" in result.output
    assert "reject" in result.output
    assert "download" in result.output
    assert "config" in result.output
    assert "logs" in result.output
    assert "serve" in result.output


def test_submit_no_description(runner: CliRunner) -> None:
    """Submit with no --description and empty stdin should fail."""
    result = runner.invoke(main, ["submit"], input="\n")
    # Either exits with error or prompts for input.
    assert result.exit_code != 0 or "Error" in result.output


@patch("colette.cli._stream_progress")
@patch("httpx.Client")
def test_submit_with_description(
    mock_client_cls: MagicMock, mock_stream: MagicMock, runner: CliRunner
) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "test-uuid"}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client
    result = runner.invoke(main, ["submit", "-d", "Build a TODO app"])
    assert result.exit_code == 0
    assert "test-uuid" in result.output


def test_config_show(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "show"])
    assert result.exit_code == 0


def test_config_validate(runner: CliRunner) -> None:
    result = runner.invoke(main, ["config", "validate"])
    assert result.exit_code == 0
    assert "valid" in result.output.lower()


# ── Submit auto-streaming (Phase 4) ─────────────────────────────────


@patch("colette.cli._stream_progress")
@patch("httpx.Client")
def test_submit_auto_streams(
    mock_client_cls: MagicMock, mock_stream: MagicMock, runner: CliRunner
) -> None:
    """Submit should call _stream_progress after POST succeeds."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "proj-aaa"}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    result = runner.invoke(main, ["submit", "-d", "Build a chat app"])
    assert result.exit_code == 0
    assert "proj-aaa" in result.output
    mock_stream.assert_called_once()
    # Verify project_id was passed
    call_args = mock_stream.call_args
    assert call_args[0][1] == "proj-aaa"  # second positional arg


@patch("colette.cli._stream_progress", side_effect=KeyboardInterrupt)
@patch("httpx.Client")
def test_submit_ctrl_c_shows_project_id(
    mock_client_cls: MagicMock, mock_stream: MagicMock, runner: CliRunner
) -> None:
    """Ctrl+C during streaming shows the project ID for later retrieval."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": "proj-bbb"}
    mock_resp.raise_for_status = MagicMock()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp
    mock_client_cls.return_value = mock_client

    result = runner.invoke(main, ["submit", "-d", "Build an app"])
    assert result.exit_code == 0
    assert "proj-bbb" in result.output
    assert "status" in result.output.lower()


# ── Status --follow uses _stream_progress (Phase 4) ─────────────────


@patch("colette.cli._stream_progress")
def test_status_follow_uses_stream_progress(
    mock_stream: MagicMock, runner: CliRunner
) -> None:
    """status --follow should delegate to _stream_progress."""
    result = runner.invoke(main, ["status", "proj-ccc", "--follow"])
    assert result.exit_code == 0
    mock_stream.assert_called_once()
    call_args = mock_stream.call_args
    assert call_args[0][1] == "proj-ccc"
