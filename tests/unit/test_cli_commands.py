"""Tests for CLI commands — approve, reject, resume, cancel, download, logs, serve."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from colette.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _mock_httpx_client(
    response_json: dict | None = None,
    status_code: int = 200,
    content: bytes = b"",
    side_effect: Exception | None = None,
) -> MagicMock:
    """Create a mock httpx.Client context manager."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = response_json or {}
    mock_resp.status_code = status_code
    mock_resp.content = content
    mock_resp.raise_for_status = MagicMock()
    if side_effect:
        mock_resp.raise_for_status.side_effect = side_effect

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_resp
    mock_client.get.return_value = mock_resp
    return mock_client


# ── Approve command ──────────────────────────────────────────────────


class TestApproveCommand:
    @patch("httpx.Client")
    def test_approve_success(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client()
        result = runner.invoke(main, ["approve", "gate-123"])
        assert result.exit_code == 0
        assert "approved" in result.output.lower()

    @patch("httpx.Client")
    def test_approve_with_comment(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client()
        result = runner.invoke(main, ["approve", "gate-123", "--comment", "LGTM"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_approve_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_cls.return_value = _mock_httpx_client(
            side_effect=httpx.HTTPError("Connection refused")
        )
        result = runner.invoke(main, ["approve", "gate-123"])
        assert result.exit_code != 0


# ── Reject command ───────────────────────────────────────────────────


class TestRejectCommand:
    @patch("httpx.Client")
    def test_reject_success(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client()
        result = runner.invoke(main, ["reject", "gate-456"])
        assert result.exit_code == 0
        assert "rejected" in result.output.lower()

    @patch("httpx.Client")
    def test_reject_with_reason(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client()
        result = runner.invoke(main, ["reject", "gate-456", "--reason", "Needs rework"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_reject_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_cls.return_value = _mock_httpx_client(side_effect=httpx.HTTPError("timeout"))
        result = runner.invoke(main, ["reject", "gate-456"])
        assert result.exit_code != 0


# ── Approvals command ────────────────────────────────────────────────


class TestApprovalsCommand:
    @patch("httpx.Client")
    def test_approvals_empty(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client(response_json=[])
        # Override .get to return a list
        client = mock_cls.return_value.__enter__.return_value
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        client.get.return_value = mock_resp
        result = runner.invoke(main, ["approvals"])
        assert result.exit_code == 0
        assert "no pending" in result.output.lower()

    @patch("httpx.Client")
    def test_approvals_with_results(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        items = [
            {
                "id": "db-id-1",
                "request_id": "req-001",
                "stage": "requirements",
                "tier": "T1",
                "status": "pending",
                "context_summary": "Requirements analysis complete",
                "created_at": "2026-04-05T10:30:00Z",
            }
        ]
        client = mock_cls.return_value.__enter__.return_value
        mock_resp = MagicMock()
        mock_resp.json.return_value = items
        mock_resp.raise_for_status = MagicMock()
        client.get.return_value = mock_resp
        result = runner.invoke(main, ["approvals"])
        assert result.exit_code == 0
        assert "req-001" in result.output

    @patch("httpx.Client")
    def test_approvals_with_project_filter(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        client = mock_cls.return_value.__enter__.return_value
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        client.get.return_value = mock_resp
        result = runner.invoke(main, ["approvals", "-p", "proj-123"])
        assert result.exit_code == 0
        # Verify project_id was passed as query param.
        call_kwargs = client.get.call_args
        assert call_kwargs[1]["params"]["project_id"] == "proj-123"

    @patch("httpx.Client")
    def test_approvals_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        client = mock_cls.return_value.__enter__.return_value
        client.get.side_effect = httpx.HTTPError("connection refused")
        result = runner.invoke(main, ["approvals"])
        assert result.exit_code != 0


# ── Resume command ───────────────────────────────────────────────────


class TestResumeCommand:
    @patch("httpx.Client")
    def test_resume_success(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client()
        result = runner.invoke(main, ["resume", "proj-aaa"])
        assert result.exit_code == 0
        assert "resumed" in result.output.lower()

    @patch("httpx.Client")
    def test_resume_404(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.json.return_value = {"detail": "Not found"}
        exc = httpx.HTTPStatusError("", request=MagicMock(), response=mock_resp)
        mock_cls.return_value = _mock_httpx_client(side_effect=exc)
        result = runner.invoke(main, ["resume", "proj-bad"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("httpx.Client")
    def test_resume_409(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {"detail": "Cannot resume."}
        exc = httpx.HTTPStatusError("", request=MagicMock(), response=mock_resp)
        mock_cls.return_value = _mock_httpx_client(side_effect=exc)
        result = runner.invoke(main, ["resume", "proj-conflict"])
        assert result.exit_code != 0

    @patch("httpx.Client")
    def test_resume_other_http_status_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError("", request=MagicMock(), response=mock_resp)
        mock_cls.return_value = _mock_httpx_client(side_effect=exc)
        result = runner.invoke(main, ["resume", "proj-500"])
        assert result.exit_code != 0

    @patch("httpx.Client")
    def test_resume_generic_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_cls.return_value = _mock_httpx_client(side_effect=httpx.HTTPError("Network error"))
        result = runner.invoke(main, ["resume", "proj-net"])
        assert result.exit_code != 0


# ── Cancel command ───────────────────────────────────────────────────


class TestCancelCommand:
    @patch("httpx.Client")
    def test_cancel_success(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client()
        result = runner.invoke(main, ["cancel", "proj-bbb"])
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

    @patch("httpx.Client")
    def test_cancel_404(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        exc = httpx.HTTPStatusError("", request=MagicMock(), response=mock_resp)
        mock_cls.return_value = _mock_httpx_client(side_effect=exc)
        result = runner.invoke(main, ["cancel", "proj-nope"])
        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    @patch("httpx.Client")
    def test_cancel_other_status_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError("", request=MagicMock(), response=mock_resp)
        mock_cls.return_value = _mock_httpx_client(side_effect=exc)
        result = runner.invoke(main, ["cancel", "proj-err"])
        assert result.exit_code != 0

    @patch("httpx.Client")
    def test_cancel_generic_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_cls.return_value = _mock_httpx_client(side_effect=httpx.HTTPError("timeout"))
        result = runner.invoke(main, ["cancel", "proj-timeout"])
        assert result.exit_code != 0


# ── Download command ─────────────────────────────────────────────────


class TestDownloadCommand:
    @patch("httpx.Client")
    def test_download_success(
        self, mock_cls: MagicMock, runner: CliRunner, tmp_path: object
    ) -> None:
        import io
        import zipfile

        # Create a valid in-memory zip
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("hello.txt", "world")
        zip_bytes = buf.getvalue()

        mock_cls.return_value = _mock_httpx_client(content=zip_bytes)
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["download", "proj-dl", "-o", "out"])
            assert result.exit_code == 0
            assert "1 files" in result.output or "Extracted" in result.output

    @patch("httpx.Client")
    def test_download_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_cls.return_value = _mock_httpx_client(side_effect=httpx.HTTPError("404"))
        result = runner.invoke(main, ["download", "proj-missing"])
        assert result.exit_code != 0


# ── Logs command ─────────────────────────────────────────────────────


class TestLogsCommand:
    @patch("httpx.Client")
    def test_logs_success(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client(
            response_json={
                "state_snapshot": {
                    "progress_events": [
                        {"stage": "requirements", "status": "completed"},
                    ],
                    "error_log": [],
                },
            }
        )
        result = runner.invoke(main, ["logs", "proj-logs"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_logs_with_stage_filter(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client(
            response_json={
                "state_snapshot": {
                    "progress_events": [
                        {"stage": "requirements", "status": "completed"},
                        {"stage": "design", "status": "completed"},
                    ],
                    "error_log": [
                        {"stage": "design", "message": "timeout"},
                    ],
                },
            }
        )
        result = runner.invoke(main, ["logs", "proj-logs", "--stage", "design"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_logs_with_errors(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client(
            response_json={
                "state_snapshot": {
                    "progress_events": [],
                    "error_log": [
                        {"stage": "testing", "message": "assertion failed"},
                    ],
                },
            }
        )
        result = runner.invoke(main, ["logs", "proj-errs"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_logs_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_cls.return_value = _mock_httpx_client(side_effect=httpx.HTTPError("fail"))
        result = runner.invoke(main, ["logs", "proj-bad"])
        assert result.exit_code != 0


# ── Status command (non-follow) ──────────────────────────────────────


class TestStatusCommand:
    @patch("httpx.Client")
    def test_status_non_follow(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client(
            response_json={"status": "running", "state_snapshot": {}}
        )
        result = runner.invoke(main, ["status", "proj-stat"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_status_interrupted_shows_notice(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client(
            response_json={"status": "interrupted", "state_snapshot": {}}
        )
        result = runner.invoke(main, ["status", "proj-int"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_status_cancelled_shows_notice(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        mock_cls.return_value = _mock_httpx_client(
            response_json={"status": "cancelled", "state_snapshot": {}}
        )
        result = runner.invoke(main, ["status", "proj-can"])
        assert result.exit_code == 0

    @patch("httpx.Client")
    def test_status_http_error(self, mock_cls: MagicMock, runner: CliRunner) -> None:
        import httpx

        mock_cls.return_value = _mock_httpx_client(side_effect=httpx.HTTPError("conn refused"))
        result = runner.invoke(main, ["status", "proj-err"])
        assert result.exit_code != 0


# ── SSE loop and streaming helpers ───────────────────────────────────


class TestRunSseLoop:
    @patch("httpx.Client")
    def test_sse_loop_http_error_returns_true(self, mock_cls: MagicMock) -> None:
        import httpx

        from colette.cli import _run_sse_loop

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.side_effect = httpx.HTTPError("fail")
        mock_cls.return_value = mock_client

        console = MagicMock()
        display = MagicMock()
        display.is_done = False

        result = _run_sse_loop("http://x", "p1", display, console, {})
        assert result is True
        console.print.assert_called_once()


class TestHandleInteractiveApproval:
    @patch("colette.cli_review.ApprovalReviewApp")
    @patch("httpx.Client")
    def test_approved_sends_requests(self, mock_cls: MagicMock, mock_app_cls: MagicMock) -> None:
        from colette.cli import _handle_interactive_approval

        mock_app_cls.return_value.run.return_value = "approved"
        mock_cls.return_value = _mock_httpx_client()
        console = MagicMock()

        result = _handle_interactive_approval(
            "http://x",
            "proj-1",
            {"request_id": "req-1", "stage": "design"},
            console,
        )
        assert result is True
        assert "Approved" in console.print.call_args[0][0]

    @patch("colette.cli_review.ApprovalReviewApp")
    @patch("httpx.Client")
    def test_rejected_sends_reject(self, mock_cls: MagicMock, mock_app_cls: MagicMock) -> None:
        from colette.cli import _handle_interactive_approval

        mock_app_cls.return_value.run.return_value = "rejected"
        mock_cls.return_value = _mock_httpx_client()
        console = MagicMock()

        result = _handle_interactive_approval(
            "http://x",
            "proj-1",
            {"request_id": "req-1"},
            console,
        )
        assert result is False

    @patch("colette.cli_review.ApprovalReviewApp")
    @patch("httpx.Client")
    def test_approved_but_resume_fails(self, mock_cls: MagicMock, mock_app_cls: MagicMock) -> None:
        import httpx

        from colette.cli import _handle_interactive_approval

        mock_app_cls.return_value.run.return_value = "approved"
        mock_cls.return_value = _mock_httpx_client(side_effect=httpx.HTTPError("resume failed"))
        console = MagicMock()

        result = _handle_interactive_approval(
            "http://x",
            "proj-1",
            {"request_id": "req-1"},
            console,
        )
        assert result is False


# ── _stream_progress ─────────────────────────────────────────────────


class TestStreamProgress:
    @patch("colette.cli._run_sse_loop", return_value=True)
    @patch("colette.cli_ui.PipelineProgressDisplay")
    @patch("colette.cli_ui.ActivityMode")
    def test_stream_done(
        self,
        mock_mode: MagicMock,
        mock_display_cls: MagicMock,
        mock_loop: MagicMock,
    ) -> None:
        from colette.cli import _stream_progress

        display = MagicMock()
        display.is_done = True
        display.render.return_value = "done"
        mock_display_cls.return_value = display
        console = MagicMock()

        _stream_progress("http://x", "proj-1", console)
        mock_loop.assert_called_once()

    @patch("colette.cli._handle_interactive_approval", return_value=False)
    @patch("colette.cli._run_sse_loop", return_value=False)
    @patch("colette.cli_ui.PipelineProgressDisplay")
    @patch("colette.cli_ui.ActivityMode")
    def test_stream_approval_rejected(
        self,
        mock_mode: MagicMock,
        mock_display_cls: MagicMock,
        mock_loop: MagicMock,
        mock_approval: MagicMock,
    ) -> None:
        from colette.cli import _stream_progress

        display = MagicMock()
        display.is_done = False
        display.pending_approval = {"request_id": "r1"}
        mock_display_cls.return_value = display
        console = MagicMock()

        _stream_progress("http://x", "proj-2", console)
        mock_approval.assert_called_once()
