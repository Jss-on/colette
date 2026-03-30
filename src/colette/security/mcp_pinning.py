"""MCP server version pinning and tool allow-listing (NFR-SEC-004, NFR-SEC-009).

Maintains a JSON registry of approved MCP server versions and their checksums.
Before connecting to an MCP server the orchestrator should call ``verify`` to
confirm the server matches the pinned version and checksum, and
``is_tool_allowed`` to confirm the requested tool is on the allow-list.
"""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class MCPPin(BaseModel):
    """Pinned metadata for a single MCP server."""

    model_config = {"frozen": True}

    server_name: str = Field(description="Canonical MCP server name.")
    version: str = Field(description="Expected semantic version.")
    checksum: str = Field(description="SHA-256 checksum of the server artifact.")
    allowed_tools: list[str] = Field(
        default_factory=list,
        description="Explicit tool allow-list for this server.",
    )


class PinVerifyResult(BaseModel):
    """Outcome of a pin verification check."""

    model_config = {"frozen": True}

    verified: bool = Field(description="Whether the server passed verification.")
    reason: str = Field(description="Human-readable explanation.")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class MCPPinRegistry:
    """Load, store, and verify MCP server pins.

    Parameters
    ----------
    pin_file:
        Path to the JSON file containing the pin entries.
    """

    def __init__(self, pin_file: str) -> None:
        self._path = Path(pin_file)
        self._pins: dict[str, MCPPin] = {}

    # -- persistence -------------------------------------------------------

    def load(self) -> None:
        """Load pin entries from disk.

        Raises ``FileNotFoundError`` if the pin file does not exist and
        ``json.JSONDecodeError`` if it is malformed.
        """
        raw = self._path.read_text(encoding="utf-8")
        data = json.loads(raw)

        pins: dict[str, MCPPin] = {}
        for entry in data:
            pin = MCPPin.model_validate(entry)
            pins[pin.server_name] = pin

        self._pins = pins
        logger.info("mcp_pins_loaded", count=len(self._pins))

    # -- verification ------------------------------------------------------

    def verify(
        self,
        server_name: str,
        version: str,
        checksum: str,
    ) -> PinVerifyResult:
        """Check *server_name* against the pinned version and checksum.

        Returns a ``PinVerifyResult`` indicating success or the reason for
        failure.
        """
        pin = self._pins.get(server_name)
        if pin is None:
            return PinVerifyResult(
                verified=False,
                reason=f"Server '{server_name}' is not in the pin registry.",
            )

        if pin.version != version:
            return PinVerifyResult(
                verified=False,
                reason=(
                    f"Version mismatch for '{server_name}': expected {pin.version}, got {version}."
                ),
            )

        if pin.checksum != checksum:
            return PinVerifyResult(
                verified=False,
                reason=(
                    f"Checksum mismatch for '{server_name}': "
                    f"expected {pin.checksum}, got {checksum}."
                ),
            )

        return PinVerifyResult(verified=True, reason="Pin verified successfully.")

    # -- tool allow-listing ------------------------------------------------

    def is_tool_allowed(self, server_name: str, tool_name: str) -> bool:
        """Return ``True`` if *tool_name* is in the allow-list for *server_name*.

        If the server has no pin entry or its allow-list is empty the tool is
        rejected (deny-by-default).
        """
        pin = self._pins.get(server_name)
        if pin is None:
            return False
        if not pin.allowed_tools:
            return False
        return tool_name in pin.allowed_tools
