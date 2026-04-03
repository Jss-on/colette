"""Artifact listing and download routes (NFR-USA-004)."""

from __future__ import annotations

import io
import uuid
import zipfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from colette.api.deps import CurrentUser, get_db, require_role
from colette.api.schemas import ArtifactListResponse, ArtifactResponse
from colette.db.repositories import ArtifactRepository, PipelineRunRepository
from colette.security.rbac import Permission

router = APIRouter()


@router.get(
    "/projects/{project_id}/artifacts",
    response_model=ArtifactListResponse,
)
async def list_artifacts(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.DOWNLOAD_ARTIFACTS))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ArtifactListResponse:
    """List artifacts for the latest pipeline run."""
    run_repo = PipelineRunRepository(db)
    runs = await run_repo.list_for_project(project_id, limit=1)
    if not runs:
        raise HTTPException(status_code=404, detail="No pipeline run found")

    art_repo = ArtifactRepository(db)
    artifacts = await art_repo.list_for_run(runs[0].id)
    return ArtifactListResponse(
        data=[
            ArtifactResponse(
                id=a.id,
                path=a.path,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
                language=a.language,
                created_at=a.created_at,
            )
            for a in artifacts
        ],
        total=len(artifacts),
    )


@router.get("/projects/{project_id}/artifacts/download")
async def download_artifacts(
    project_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(require_role(Permission.DOWNLOAD_ARTIFACTS))],
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    """Download all artifacts as a zip file.

    Reads ``GeneratedFile`` objects from the pipeline state snapshot
    and bundles them into a zip archive streamed to the client.
    """
    run_repo = PipelineRunRepository(db)
    runs = await run_repo.list_for_project(project_id, limit=1)
    if not runs:
        raise HTTPException(status_code=404, detail="No pipeline run found")

    state = runs[0].state_snapshot or {}

    # Collect generated files from both metadata and handoffs.
    generated_files: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    # Primary source: metadata.generated_files (has full file content).
    metadata_files = state.get("metadata", {}).get("generated_files", {})
    def _is_valid_file(f: object) -> bool:
        return isinstance(f, dict) and "path" in f and "content" in f

    for stage_files in metadata_files.values():
        if isinstance(stage_files, list):
            for f in stage_files:
                if _is_valid_file(f) and f["path"] not in seen_paths:
                    generated_files.append(f)
                    seen_paths.add(f["path"])

    # Fallback: handoffs.*.generated_files (older format).
    for stage_data in state.get("handoffs", {}).values():
        if isinstance(stage_data, dict):
            for f in stage_data.get("generated_files", []):
                if _is_valid_file(f) and f["path"] not in seen_paths:
                    generated_files.append(f)
                    seen_paths.add(f["path"])

    if not generated_files:
        raise HTTPException(status_code=404, detail="No generated files found")

    # Build zip in memory.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in generated_files:
            zf.writestr(f["path"], f.get("content", ""))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="colette-{project_id}.zip"',
        },
    )
