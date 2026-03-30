"""Immutable append-only audit log (NFR-SEC-005).

Entries are serialized as one JSON object per line (JSONL) and appended to an
audit file.  The log is designed for compliance and forensic traceability.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


class AuditEntry(BaseModel):
    """Single immutable audit record."""

    model_config = {"frozen": True}

    entry_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique entry identifier (UUID4).",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the event.",
    )
    actor_id: str = Field(description="Identifier of the user or agent that acted.")
    actor_role: str = Field(description="Role of the actor at the time of action.")
    action: str = Field(description="Action that was performed (e.g. 'deploy').")
    resource: str = Field(
        description="Resource the action targeted (e.g. 'pipeline:abc123').",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured context about the event.",
    )
    outcome: str = Field(
        description="Result of the action: 'success' or 'failure'.",
    )
    project_id: str | None = Field(
        default=None,
        description="Optional project scope for the event.",
    )


# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Append-only JSONL audit logger.

    Parameters
    ----------
    log_path:
        File path for the JSONL audit log.  Parent directories are created
        automatically on first write.
    """

    def __init__(self, log_path: str) -> None:
        self._path = Path(log_path)

    # -- write -------------------------------------------------------------

    def log(self, entry: AuditEntry) -> None:
        """Append *entry* as a single JSON line.

        Uses append mode so concurrent writers do not clobber each other on
        most operating systems (including Windows with default buffering).
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        line = entry.model_dump_json() + "\n"
        with self._path.open(mode="a", encoding="utf-8") as fh:
            fh.write(line)
        logger.debug("audit_entry_written", entry_id=entry.entry_id, action=entry.action)

    # -- read / query ------------------------------------------------------

    def query(
        self,
        *,
        actor_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Read and filter audit entries.

        Parameters
        ----------
        actor_id:
            Filter by actor.
        action:
            Filter by action name.
        since:
            Only entries at or after this timestamp.
        limit:
            Maximum entries to return (most-recent first after filtering).
        """
        if not self._path.exists():
            return []

        entries: list[AuditEntry] = []
        with self._path.open(encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                except json.JSONDecodeError:
                    logger.warning("audit_corrupt_line", line=stripped[:120])
                    continue
                entry = AuditEntry.model_validate(data)
                if actor_id is not None and entry.actor_id != actor_id:
                    continue
                if action is not None and entry.action != action:
                    continue
                if since is not None and entry.timestamp < since:
                    continue
                entries.append(entry)

        # Return most-recent entries first, capped at *limit*.
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]
