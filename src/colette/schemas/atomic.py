"""Data structures for atomic code generation units."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from colette.schemas.common import (
    ComponentSpec,
    EndpointSpec,
    EntitySpec,
    GeneratedFile,
)

# ── Unit classification ──────────────────────────────────────────────────


class AtomicUnitKind(StrEnum):
    """The domain category of an atomic generation unit."""

    SCAFFOLDING = "scaffolding"
    DATABASE_ENTITY = "database_entity"
    BACKEND_ENDPOINT = "backend_endpoint"
    FRONTEND_COMPONENT = "frontend_component"


# ── Unit specification (input to generation) ─────────────────────────────


class AtomicUnitSpec(BaseModel, frozen=True):
    """Describes one atomic unit to be generated.

    Each spec maps to exactly one LLM call that produces a small,
    focused set of files for a single entity/endpoint/component.
    """

    kind: AtomicUnitKind
    name: str = Field(description="Human-readable identifier (e.g. 'User', 'GET /api/todos').")
    entity_spec: EntitySpec | None = Field(default=None, description="Set for DATABASE_ENTITY.")
    endpoint_spec: EndpointSpec | None = Field(
        default=None, description="Set for BACKEND_ENDPOINT."
    )
    component_spec: ComponentSpec | None = Field(
        default=None, description="Set for FRONTEND_COMPONENT."
    )
    depends_on: tuple[str, ...] = Field(
        default_factory=tuple,
        description="Names of units that must be generated before this one.",
    )
    phase: int = Field(
        default=0,
        ge=0,
        le=3,
        description="Generation phase: 0=scaffold, 1=database, 2=backend, 3=frontend.",
    )


# ── Per-unit output models (one per LLM call) ───────────────────────────


class AtomicScaffoldUnit(BaseModel, frozen=True):
    """Output from scaffolding generation (config files, package manifests)."""

    files: list[GeneratedFile] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    notes: str = ""


class AtomicDatabaseUnit(BaseModel, frozen=True):
    """Output from a single database entity generation."""

    files: list[GeneratedFile] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    notes: str = ""


class AtomicBackendUnit(BaseModel, frozen=True):
    """Output from a single backend endpoint generation."""

    files: list[GeneratedFile] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    notes: str = ""


class AtomicFrontendUnit(BaseModel, frozen=True):
    """Output from a single frontend component generation."""

    files: list[GeneratedFile] = Field(default_factory=list)
    packages: list[str] = Field(default_factory=list)
    env_vars: list[str] = Field(default_factory=list)
    notes: str = ""


# Type alias for the union of all unit output types.
AtomicUnitOutput = AtomicScaffoldUnit | AtomicDatabaseUnit | AtomicBackendUnit | AtomicFrontendUnit


# ── Unit result (output + verification status) ──────────────────────────


class AtomicUnitResult(BaseModel):
    """Wraps a generated unit with its verification outcome."""

    spec: AtomicUnitSpec
    output: AtomicUnitOutput
    verified: bool = False
    verification_errors: list[str] = Field(default_factory=list)
    fix_attempts: int = 0


# ── Generation progress (accumulator) ────────────────────────────────────


class AtomicGenerationProgress(BaseModel):
    """Accumulates results across all atomic units in a generation run."""

    completed: list[AtomicUnitResult] = Field(default_factory=list)
    failed: list[AtomicUnitResult] = Field(default_factory=list)
    all_files: list[GeneratedFile] = Field(default_factory=list)
    all_packages: list[str] = Field(default_factory=list)
    all_env_vars: list[str] = Field(default_factory=list)

    def add_result(self, result: AtomicUnitResult) -> None:
        """Record a completed unit, accumulating files/packages/env_vars."""
        if result.verified:
            self.completed.append(result)
        else:
            self.failed.append(result)
        self.all_files.extend(result.output.files)
        for pkg in result.output.packages:
            if pkg not in self.all_packages:
                self.all_packages.append(pkg)
        for var in result.output.env_vars:
            if var not in self.all_env_vars:
                self.all_env_vars.append(var)
