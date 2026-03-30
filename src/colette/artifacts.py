"""Artifact packaging — zip generation from pipeline output (NFR-USA-004)."""

from __future__ import annotations

import io
import zipfile
from typing import Any


def collect_generated_files(state: dict[str, Any]) -> list[dict[str, str]]:
    """Extract ``GeneratedFile``-like dicts from pipeline state handoffs."""
    files: list[dict[str, str]] = []
    for stage_data in state.get("handoffs", {}).values():
        for f in stage_data.get("generated_files", []):
            if isinstance(f, dict) and "path" in f and "content" in f:
                files.append(f)
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
