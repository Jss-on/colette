"""Implementation → Testing handoff schema (FR-ORC-020, §6)."""

from __future__ import annotations

from pydantic import Field

from colette.schemas.base import HandoffSchema
from colette.schemas.common import EndpointSpec, FileDiff


class ImplementationToTestingHandoff(HandoffSchema):
    """Structured output of the Implementation stage consumed by Testing."""

    source_stage: str = "implementation"
    target_stage: str = "testing"
    schema_version: str = "1.0.0"

    # ── Git (FR-IMP-005) ─────────────────────────────────────────────
    git_repo_url: str = Field(description="URL of the Git repository.")
    git_ref: str = Field(description="Branch or commit SHA to test.")
    commit_shas: list[str] = Field(default_factory=list)

    # ── Changed files (FR-IMP-006) ───────────────────────────────────
    files_changed: list[FileDiff] = Field(default_factory=list)

    # ── API contract (FR-IMP-009) ────────────────────────────────────
    implemented_endpoints: list[EndpointSpec] = Field(default_factory=list)
    openapi_spec_ref: str = Field(
        default="",
        description="Path or ref to the OpenAPI spec from Design stage.",
    )

    # ── Environment ──────────────────────────────────────────────────
    env_vars: list[str] = Field(
        default_factory=list,
        description="Required env var names (not values).",
    )
    docker_compose_path: str = ""
    readme_path: str = ""

    # ── Quality signals ──────────────────────────────────────────────
    lint_passed: bool = False
    type_check_passed: bool = False
    build_passed: bool = False

    # ── Test hints ───────────────────────────────────────────────────
    test_hints: list[str] = Field(
        default_factory=list,
        description="Hints for the Testing stage: edge cases, critical paths.",
    )
