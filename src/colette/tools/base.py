"""Base MCP tool wrapper with sanitization and auditing (FR-TL-001/004/005).

All Colette tools extend ``MCPBaseTool`` which wraps every invocation
with output sanitization (prompt-injection defense) and structured audit
logging.
"""

from __future__ import annotations

import re
import time
from abc import abstractmethod
from typing import Any

import structlog
from langchain_core.tools import BaseTool

logger = structlog.get_logger(__name__)

# ── Prompt-injection markers to strip (FR-TL-004) ──────────────────

_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"<\|user\|>", re.IGNORECASE),
    re.compile(r"<\|assistant\|>", re.IGNORECASE),
    re.compile(r"\[INST\]", re.IGNORECASE),
    re.compile(r"\[/INST\]", re.IGNORECASE),
    re.compile(r"\n\nHuman:", re.IGNORECASE),
    re.compile(r"\n\nAssistant:", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
]

# Keys whose values should be redacted in audit logs
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "api_secret",
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "private_key",
        "credential",
        "credentials",
    }
)

_REDACTED = "***REDACTED***"


def sanitize_output(text: str) -> str:
    """Strip known prompt-injection markers from tool output (FR-TL-004)."""
    result = text
    for pattern in _INJECTION_PATTERNS:
        result = pattern.sub("", result)
    return result


def redact_secrets(params: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *params* with secret values replaced (FR-TL-005)."""
    return {k: _REDACTED if k.lower() in _SECRET_KEYS else v for k, v in params.items()}


def validate_path(raw: str) -> str:
    """Reject path traversal attempts (FR-TL-004).

    Returns the cleaned path string, or raises ``ValueError``
    if the path contains ``..`` segments.
    """
    from pathlib import PurePosixPath, PureWindowsPath

    for cls in (PurePosixPath, PureWindowsPath):
        if ".." in cls(raw).parts:
            raise ValueError(f"Path traversal rejected: {raw!r}")
    return raw


class MCPBaseTool(BaseTool):
    """Base class for MCP-wrapped tools with sanitization and auditing.

    Subclasses implement ``_execute()``; this class handles:
    - Output sanitization (FR-TL-004)
    - Structured audit logging (FR-TL-005)
    """

    sanitize: bool = True

    def _run(self, **kwargs: Any) -> str:
        """Run the tool with sanitization and audit logging."""
        start = time.monotonic()
        success = True
        error_msg: str | None = None
        result = ""

        try:
            result = self._execute(**kwargs)
        except Exception as exc:
            success = False
            error_msg = str(exc)
            raise
        finally:
            latency_ms = (time.monotonic() - start) * 1000
            logger.info(
                "tool_call",
                tool_name=self.name,
                params=redact_secrets(kwargs),
                output_length=len(result),
                latency_ms=round(latency_ms, 2),
                success=success,
                error=error_msg,
            )

        if self.sanitize:
            result = sanitize_output(result)
        return result

    @abstractmethod
    def _execute(self, **kwargs: Any) -> str:
        """Execute the tool operation.  Implemented by subclasses."""
        ...
