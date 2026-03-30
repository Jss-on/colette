"""Tests for implementation tools (Phase 5) — linter, type_checker, dependency_audit, npm."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from colette.tools.base import validate_path
from colette.tools.dependency_audit import DependencyAuditTool
from colette.tools.linter import LinterTool
from colette.tools.npm import NpmTool
from colette.tools.type_checker import TypeCheckerTool

# ── validate_path ───────────────────────────────────────────────────────


class TestValidatePath:
    def test_accepts_simple_path(self) -> None:
        assert validate_path("src/app.py") == "src/app.py"

    def test_accepts_dot(self) -> None:
        assert validate_path(".") == "."

    def test_rejects_dotdot(self) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            validate_path("../../etc/passwd")

    def test_rejects_embedded_dotdot(self) -> None:
        with pytest.raises(ValueError, match="Path traversal"):
            validate_path("src/../../../secrets")


# ── LinterTool ──────────────────────────────────────────────────────────


class TestLinterTool:
    def test_python_lint_pass(self) -> None:
        tool = LinterTool()
        with patch("colette.tools.linter.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "All checks passed!"
            mock_run.return_value.stderr = ""
            result = tool._run(path="src/", language="python")
        assert "LINT PASSED" in result
        mock_run.assert_called_once()
        assert "ruff" in mock_run.call_args[0][0]

    def test_python_lint_fail(self) -> None:
        tool = LinterTool()
        with patch("colette.tools.linter.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = "E501 line too long"
            mock_run.return_value.stderr = ""
            result = tool._run(path="src/", language="python")
        assert "LINT FAILED" in result
        assert "E501" in result

    def test_typescript_uses_eslint(self) -> None:
        tool = LinterTool()
        with patch("colette.tools.linter.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "No problems"
            mock_run.return_value.stderr = ""
            tool._run(path="src/", language="typescript")
        assert "eslint" in mock_run.call_args[0][0]

    def test_unsupported_language(self) -> None:
        tool = LinterTool()
        result = tool._run(path="src/", language="rust")
        assert "Unsupported" in result

    def test_tool_not_found(self) -> None:
        tool = LinterTool()
        with patch("colette.tools.linter.subprocess.run", side_effect=FileNotFoundError):
            result = tool._run(path="src/", language="python")
        assert "not found" in result


# ── TypeCheckerTool ─────────────────────────────────────────────────────


class TestTypeCheckerTool:
    def test_python_pass(self) -> None:
        tool = TypeCheckerTool()
        with patch("colette.tools.type_checker.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Success: no issues found"
            mock_run.return_value.stderr = ""
            result = tool._run(path="src/", language="python")
        assert "TYPE CHECK PASSED" in result
        assert "mypy" in mock_run.call_args[0][0]

    def test_typescript_uses_tsc(self) -> None:
        tool = TypeCheckerTool()
        with patch("colette.tools.type_checker.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            tool._run(path="src/", language="typescript")
        assert "tsc" in mock_run.call_args[0][0]

    def test_unsupported_language(self) -> None:
        tool = TypeCheckerTool()
        result = tool._run(path="src/", language="go")
        assert "Unsupported" in result


# ── DependencyAuditTool ─────────────────────────────────────────────────


class TestDependencyAuditTool:
    def test_python_audit_pass(self) -> None:
        tool = DependencyAuditTool()
        with patch("colette.tools.dependency_audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "No known vulnerabilities found"
            mock_run.return_value.stderr = ""
            result = tool._run(path=".", language="python")
        assert "AUDIT PASSED" in result
        assert "pip-audit" in mock_run.call_args[0][0]

    def test_js_audit_uses_npm(self) -> None:
        tool = DependencyAuditTool()
        with patch("colette.tools.dependency_audit.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "{}"
            mock_run.return_value.stderr = ""
            tool._run(path=".", language="javascript")
        assert "npm" in mock_run.call_args[0][0]

    def test_unsupported_language(self) -> None:
        tool = DependencyAuditTool()
        result = tool._run(path=".", language="ruby")
        assert "Unsupported" in result


# ── NpmTool ─────────────────────────────────────────────────────────────


class TestNpmTool:
    def test_install_command(self) -> None:
        tool = NpmTool()
        with patch("colette.tools.npm.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "added 50 packages"
            mock_run.return_value.stderr = ""
            result = tool._run(command="install", cwd=".")
        assert "EXIT 0" in result
        assert "added 50 packages" in result

    def test_blocked_command(self) -> None:
        tool = NpmTool()
        result = tool._run(command="publish")
        assert "not allowed" in result

    def test_with_args(self) -> None:
        tool = NpmTool()
        with patch("colette.tools.npm.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ok"
            mock_run.return_value.stderr = ""
            tool._run(command="install", args=["react", "--save"])
        cmd = mock_run.call_args[0][0]
        assert "react" in cmd
        assert "--save" in cmd

    def test_npm_not_found(self) -> None:
        tool = NpmTool()
        with patch("colette.tools.npm.subprocess.run", side_effect=FileNotFoundError):
            result = tool._run(command="install")
        assert "not found" in result

    def test_non_list_args_coerced(self) -> None:
        tool = NpmTool()
        with patch("colette.tools.npm.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "ok"
            mock_run.return_value.stderr = ""
            # Pass a string instead of list — should be safely coerced to []
            tool._run(command="install", args="--save")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["npm", "install"]

    def test_path_traversal_rejected(self) -> None:
        tool = NpmTool()
        with pytest.raises(ValueError, match="Path traversal"):
            tool._run(command="install", cwd="../../etc")
