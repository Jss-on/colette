"""Artifact packaging — zip generation from pipeline output (NFR-USA-004)."""

from __future__ import annotations

import io
import zipfile
from typing import Any


def collect_generated_files(state: dict[str, Any]) -> list[dict[str, str]]:
    """Extract ``GeneratedFile``-like dicts from pipeline state.

    Checks both ``metadata.generated_files`` (primary, written by stages)
    and ``handoffs.*.generated_files`` (fallback) with path-based dedup.
    """
    files: list[dict[str, str]] = []
    seen: set[str] = set()

    def _valid(f: object) -> bool:
        return isinstance(f, dict) and "path" in f and "content" in f

    # Primary: metadata.generated_files (per-stage lists)
    for stage_files in state.get("metadata", {}).get("generated_files", {}).values():
        if isinstance(stage_files, list):
            for f in stage_files:
                if _valid(f) and f["path"] not in seen:
                    files.append(f)
                    seen.add(f["path"])

    # Fallback: handoffs.*.generated_files
    for stage_data in state.get("handoffs", {}).values():
        if isinstance(stage_data, dict):
            for f in stage_data.get("generated_files", []):
                if _valid(f) and f["path"] not in seen:
                    files.append(f)
                    seen.add(f["path"])

    return files


def create_artifact_zip(files: list[dict[str, str]]) -> bytes:
    """Create a zip archive from a list of ``{path, content}`` dicts.

    Returns the zip file contents as bytes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.writestr(f["path"], f.get("content", ""))
    return buf.getvalue()
