"""Atomic code generation — one entity/endpoint/component at a time.

Instead of generating all files per agent in one massive LLM call,
this module breaks generation into small, focused units that are
each verified before moving on. Mirrors how a real developer works:
scaffold → database → backend → frontend, one piece at a time.
"""

from __future__ import annotations

import heapq
import re
from typing import TYPE_CHECKING

import structlog

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.atomic import (
    AtomicBackendUnit,
    AtomicDatabaseUnit,
    AtomicFrontendUnit,
    AtomicGenerationProgress,
    AtomicScaffoldUnit,
    AtomicUnitKind,
    AtomicUnitOutput,
    AtomicUnitResult,
    AtomicUnitSpec,
)
from colette.schemas.common import GeneratedFile
from colette.stages.implementation.prompts import (
    ATOMIC_BACKEND_ENDPOINT_PROMPT,
    ATOMIC_DATABASE_ENTITY_PROMPT,
    ATOMIC_FRONTEND_COMPONENT_PROMPT,
    ATOMIC_SCAFFOLDING_PROMPT,
)
from colette.stages.implementation.verifier import (
    filter_findings_to_paths,
    verify_generated_code,
)

if TYPE_CHECKING:
    from colette.config import Settings
    from colette.schemas.design import DesignToImplementationHandoff
    from colette.schemas.module_design import ModuleDesign

logger = structlog.get_logger(__name__)

# ── Unit extraction ──────────────────────────────────────────────────────


def extract_atomic_units(
    handoff: DesignToImplementationHandoff,
    module_design: ModuleDesign | None,
) -> list[AtomicUnitSpec]:
    """Extract atomic generation units from design artifacts.

    Produces one unit per scaffolding task, DB entity, API endpoint,
    and UI component. Dependency edges are derived from entity
    relationships, auth requirements, and component hierarchies.
    """
    units: list[AtomicUnitSpec] = []

    # Phase 0: Scaffolding (single unit)
    units.append(
        AtomicUnitSpec(
            kind=AtomicUnitKind.SCAFFOLDING,
            name="project_scaffold",
            phase=0,
        )
    )

    # Phase 1: Database entities — FK-ordered
    entity_names = {e.name for e in handoff.db_entities}
    for entity in handoff.db_entities:
        # Dependencies: other entities referenced in relationships
        deps: list[str] = []
        for rel in entity.relationships:
            # Extract referenced entity name from relationship strings
            # e.g. "belongs_to:User" or "User.id" or "FK -> users"
            for other in entity_names:
                if other != entity.name and other.lower() in rel.lower():
                    deps.append(other)
        units.append(
            AtomicUnitSpec(
                kind=AtomicUnitKind.DATABASE_ENTITY,
                name=entity.name,
                entity_spec=entity,
                depends_on=tuple(deps),
                phase=1,
            )
        )

    # Phase 2: Backend endpoints — auth endpoints first
    auth_endpoints: list[AtomicUnitSpec] = []
    protected_endpoints: list[AtomicUnitSpec] = []
    for ep in handoff.endpoints:
        ep_name = f"{ep.method} {ep.path}"
        is_auth = _is_auth_endpoint(ep.path, ep.summary)
        spec = AtomicUnitSpec(
            kind=AtomicUnitKind.BACKEND_ENDPOINT,
            name=ep_name,
            endpoint_spec=ep,
            depends_on=tuple(
                # Auth endpoints have no deps; protected endpoints depend on auth endpoints
                [] if is_auth else [s.name for s in auth_endpoints]
            ),
            phase=2,
        )
        if is_auth:
            auth_endpoints.append(spec)
        else:
            protected_endpoints.append(spec)
    units.extend(auth_endpoints)
    units.extend(protected_endpoints)

    # Phase 3: Frontend components — leaf components before pages
    component_children: dict[str, list[str]] = {}
    for comp in handoff.ui_components:
        component_children[comp.name] = list(comp.children)

    for comp in handoff.ui_components:
        # Depend on child components (leaf-first ordering)
        deps = [child for child in comp.children if child in component_children]
        units.append(
            AtomicUnitSpec(
                kind=AtomicUnitKind.FRONTEND_COMPONENT,
                name=comp.name,
                component_spec=comp,
                depends_on=tuple(deps),
                phase=3,
            )
        )

    return units


def _is_auth_endpoint(path: str, summary: str) -> bool:
    """Heuristic: detect auth-related endpoints by path or summary."""
    combined = f"{path} {summary}".lower()
    return bool(re.search(r"(auth|login|register|signup|token|session)", combined))


# ── Topological sort ─────────────────────────────────────────────────────


def topological_sort_units(units: list[AtomicUnitSpec]) -> list[AtomicUnitSpec]:
    """Sort units respecting dependencies, with secondary sort by phase then name.

    Uses a priority-queue (min-heap) BFS so that among nodes whose
    dependencies are all satisfied, the one with the smallest
    ``(phase, name)`` is emitted first.  This guarantees deterministic
    output that honours both dependency constraints and the preferred
    phase → alphabetical ordering.
    """
    by_name = {u.name: u for u in units}
    # Build adjacency: only include deps present in our unit set
    graph: dict[str, set[str]] = {u.name: {d for d in u.depends_on if d in by_name} for u in units}
    in_degree = {name: len(deps) for name, deps in graph.items()}
    dependents: dict[str, list[str]] = {name: [] for name in graph}
    for name, deps in graph.items():
        for dep in deps:
            dependents[dep].append(name)

    # Seed the heap with zero-in-degree nodes
    ready: list[tuple[int, str]] = [
        (by_name[n].phase, n) for n, deg in in_degree.items() if deg == 0
    ]
    heapq.heapify(ready)

    result: list[AtomicUnitSpec] = []
    while ready:
        _phase, name = heapq.heappop(ready)
        result.append(by_name[name])
        for dep_name in dependents[name]:
            in_degree[dep_name] -= 1
            if in_degree[dep_name] == 0:
                heapq.heappush(ready, (by_name[dep_name].phase, dep_name))

    return result


# ── Incremental context builder ──────────────────────────────────────────

_DOMAIN_MAP: dict[AtomicUnitKind, str] = {
    AtomicUnitKind.SCAFFOLDING: "scaffold",
    AtomicUnitKind.DATABASE_ENTITY: "database",
    AtomicUnitKind.BACKEND_ENDPOINT: "backend",
    AtomicUnitKind.FRONTEND_COMPONENT: "frontend",
}

_ADJACENT: dict[str, set[str]] = {
    "scaffold": {"database", "backend", "frontend"},
    "database": {"backend"},
    "backend": {"database", "frontend"},
    "frontend": {"backend"},
}


def _extract_signatures(content: str) -> str:
    """Extract function/class signatures from file content (first 3 lines of each def/class)."""
    lines = content.split("\n")
    sig_lines: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if stripped.startswith(("def ", "class ", "async def ", "export ", "interface ", "type ")):
            sig_lines.append(lines[i])
            # Include up to 2 more lines for the signature
            for j in range(1, 3):
                if i + j < len(lines):
                    sig_lines.append(lines[i + j])
            sig_lines.append("")
        i += 1
    return "\n".join(sig_lines) if sig_lines else content[:200]


def build_incremental_context(
    design_context: str,
    verified_files: list[GeneratedFile],
    current_spec: AtomicUnitSpec,
    *,
    max_context_chars: int = 60_000,
) -> str:
    """Build tiered context from previously verified files.

    Tier 1 (same domain): full file content
    Tier 2 (adjacent domain): signatures only
    Tier 3 (distant domain): file paths only

    Truncation: drop Tier 3 first, then Tier 2 oldest-first,
    then Tier 1 oldest-first. Never truncate the current unit spec.
    """
    current_domain = _DOMAIN_MAP[current_spec.kind]
    adjacent = _ADJACENT.get(current_domain, set())

    tier1: list[str] = []  # Same domain — full content
    tier2: list[str] = []  # Adjacent — signatures
    tier3: list[str] = []  # Distant — paths only

    for f in verified_files:
        domain = _classify_file_domain(f.path)
        if domain == current_domain:
            tier1.append(f"### {f.path}\n```{f.language}\n{f.content}\n```")
        elif domain in adjacent:
            sigs = _extract_signatures(f.content)
            tier2.append(f"### {f.path} (signatures)\n```{f.language}\n{sigs}\n```")
        else:
            tier3.append(f"- {f.path}")

    # Build context sections
    sections = [design_context]

    # Add unit spec details
    spec_section = _format_unit_spec(current_spec)
    sections.append(spec_section)

    # Add tiers (budget-aware)
    budget = max_context_chars - sum(len(s) for s in sections)

    if tier1:
        t1_text = "\n\n## Previously Generated (Same Domain)\n\n" + "\n\n".join(tier1)
        if len(t1_text) <= budget:
            sections.append(t1_text)
            budget -= len(t1_text)
        else:
            # Truncate oldest first
            partial = "\n\n## Previously Generated (Same Domain)\n\n"
            for block in reversed(tier1):
                if len(partial) + len(block) + 2 < budget:
                    partial = partial + block + "\n\n"
            sections.append(partial)
            budget -= len(partial)

    if tier2 and budget > 500:
        t2_text = "\n\n## Adjacent Domain (Signatures)\n\n" + "\n\n".join(tier2)
        if len(t2_text) <= budget:
            sections.append(t2_text)
            budget -= len(t2_text)

    if tier3 and budget > 200:
        t3_text = "\n\n## Other Files\n\n" + "\n".join(tier3)
        if len(t3_text) <= budget:
            sections.append(t3_text)

    return "\n\n".join(sections)


def _classify_file_domain(path: str) -> str:
    """Classify a file path into a domain."""
    lower = path.lower()
    if any(
        k in lower
        for k in ("migration", "schema", "seed", "models/", "alembic", "prisma", "entity")
    ):
        return "database"
    if any(
        k in lower
        for k in (
            "component",
            "page",
            "hook",
            ".tsx",
            ".jsx",
            "frontend/",
            "client/",
            "src/app/",
        )
    ):
        return "frontend"
    if any(
        k in lower
        for k in ("route", "handler", "middleware", "service", "controller", "api/", "backend/")
    ):
        return "backend"
    if any(
        k in lower
        for k in ("package.json", "pyproject.toml", "tsconfig", "docker", ".env", "config")
    ):
        return "scaffold"
    return "backend"  # default


def _format_unit_spec(spec: AtomicUnitSpec) -> str:
    """Format the current unit spec as context for the LLM."""
    sections = [f"## Current Unit: {spec.name} ({spec.kind.value})"]
    if spec.entity_spec:
        e = spec.entity_spec
        fields = ", ".join(f"{f['name']} ({f['type']})" for f in e.fields)
        sections.append(f"Entity: {e.name}\nFields: {fields}")
        if e.indexes:
            sections.append(f"Indexes: {', '.join(e.indexes)}")
        if e.relationships:
            sections.append(f"Relationships: {', '.join(e.relationships)}")
    if spec.endpoint_spec:
        ep = spec.endpoint_spec
        auth = " [auth required]" if ep.auth_required else ""
        sections.append(f"Endpoint: {ep.method} {ep.path}{auth}\nSummary: {ep.summary}")
        if ep.request_schema:
            sections.append(f"Request schema: {ep.request_schema}")
        if ep.response_schema:
            sections.append(f"Response schema: {ep.response_schema}")
    if spec.component_spec:
        c = spec.component_spec
        sections.append(f"Component: {c.name}\nDescription: {c.description}")
        if c.props:
            props = ", ".join(f"{p.get('name', '?')}: {p.get('type', '?')}" for p in c.props)
            sections.append(f"Props: {props}")
        if c.route:
            sections.append(f"Route: {c.route}")
        if c.children:
            sections.append(f"Children: {', '.join(c.children)}")
    return "\n".join(sections)


# ── Generation functions (one per unit kind) ─────────────────────────────

_KIND_TO_PROMPT: dict[AtomicUnitKind, str] = {
    AtomicUnitKind.SCAFFOLDING: ATOMIC_SCAFFOLDING_PROMPT,
    AtomicUnitKind.DATABASE_ENTITY: ATOMIC_DATABASE_ENTITY_PROMPT,
    AtomicUnitKind.BACKEND_ENDPOINT: ATOMIC_BACKEND_ENDPOINT_PROMPT,
    AtomicUnitKind.FRONTEND_COMPONENT: ATOMIC_FRONTEND_COMPONENT_PROMPT,
}

_KIND_TO_OUTPUT: dict[AtomicUnitKind, type[AtomicUnitOutput]] = {
    AtomicUnitKind.SCAFFOLDING: AtomicScaffoldUnit,
    AtomicUnitKind.DATABASE_ENTITY: AtomicDatabaseUnit,
    AtomicUnitKind.BACKEND_ENDPOINT: AtomicBackendUnit,
    AtomicUnitKind.FRONTEND_COMPONENT: AtomicFrontendUnit,
}


async def _generate_unit(
    spec: AtomicUnitSpec,
    context: str,
    *,
    settings: Settings,
) -> AtomicUnitOutput:
    """Generate files for a single atomic unit via structured LLM call."""
    prompt = _KIND_TO_PROMPT[spec.kind]
    output_type = _KIND_TO_OUTPUT[spec.kind]

    return await invoke_structured(
        system_prompt=prompt,
        user_content=context,
        output_type=output_type,
        settings=settings,
        model_tier=ModelTier.EXECUTION,
    )


# ── Verify and fix (per unit) ────────────────────────────────────────────


async def verify_and_fix_unit(
    unit_result: AtomicUnitResult,
    all_prior_files: list[GeneratedFile],
    *,
    settings: Settings,
    max_fix_attempts: int = 2,
) -> AtomicUnitResult:
    """Verify a single unit's files and attempt fixes if needed.

    Uses deterministic eval if available (graceful import fallback),
    else LLM-based verification filtered to the unit's file paths.
    """
    unit_paths = {f.path for f in unit_result.output.files}
    if not unit_paths:
        return AtomicUnitResult(
            spec=unit_result.spec,
            output=unit_result.output,
            verified=True,
        )

    # Verify: all files (prior + current) for full-picture, then filter
    all_files = [*all_prior_files, *unit_result.output.files]
    report = await verify_generated_code(all_files, settings=settings)
    filtered = filter_findings_to_paths(report, unit_paths)

    if filtered.lint_passed and filtered.type_check_passed and filtered.build_passed:
        return AtomicUnitResult(
            spec=unit_result.spec,
            output=unit_result.output,
            verified=True,
        )

    errors = [f"[{f.category}] {f.file_path}: {f.message}" for f in filtered.findings]

    # Attempt fixes
    from colette.stages.implementation.verifier import fix_files

    current_files = list(unit_result.output.files)
    for attempt in range(1, max_fix_attempts + 1):
        logger.info(
            "atomic.fix_attempt",
            unit=unit_result.spec.name,
            attempt=attempt,
            errors=len(errors),
        )
        fixed = await fix_files(current_files, filtered, settings=settings)
        if fixed:
            current_files = fixed

        # Re-verify
        all_files_updated = [*all_prior_files, *current_files]
        report = await verify_generated_code(all_files_updated, settings=settings)
        filtered = filter_findings_to_paths(report, {f.path for f in current_files})

        if filtered.lint_passed and filtered.type_check_passed and filtered.build_passed:
            # Rebuild output with fixed files
            output_type = type(unit_result.output)
            new_output = output_type(
                files=current_files,
                packages=list(unit_result.output.packages),
                env_vars=list(unit_result.output.env_vars),
                notes=unit_result.output.notes,
            )
            return AtomicUnitResult(
                spec=unit_result.spec,
                output=new_output,
                verified=True,
                fix_attempts=attempt,
            )

        errors = [f"[{f.category}] {f.file_path}: {f.message}" for f in filtered.findings]

    # Exhausted fix attempts — return best effort
    output_type = type(unit_result.output)
    new_output = output_type(
        files=current_files,
        packages=list(unit_result.output.packages),
        env_vars=list(unit_result.output.env_vars),
        notes=unit_result.output.notes,
    )
    return AtomicUnitResult(
        spec=unit_result.spec,
        output=new_output,
        verified=False,
        verification_errors=errors,
        fix_attempts=max_fix_attempts,
    )


# ── Main orchestration loop ──────────────────────────────────────────────


async def run_atomic_generation(
    handoff: DesignToImplementationHandoff,
    design_context: str,
    module_design: ModuleDesign | None,
    *,
    settings: Settings,
) -> AtomicGenerationProgress:
    """Run atomic generation: extract → sort → generate each → verify → accumulate.

    This is the main entry point for the atomic code generation path.
    """
    logger.info("atomic_generation.start")

    # Extract and sort units
    units = extract_atomic_units(handoff, module_design)
    sorted_units = topological_sort_units(units)

    logger.info(
        "atomic_generation.units_extracted",
        total=len(sorted_units),
        phases={p: sum(1 for u in sorted_units if u.phase == p) for p in range(4)},
    )

    progress = AtomicGenerationProgress()
    verified_files: list[GeneratedFile] = []
    max_fixes = settings.atomic_max_fix_attempts

    for i, spec in enumerate(sorted_units):
        logger.info(
            "atomic_generation.unit_start",
            unit=spec.name,
            kind=spec.kind.value,
            phase=spec.phase,
            index=i + 1,
            total=len(sorted_units),
        )

        # Build context with incremental knowledge from prior units
        context = build_incremental_context(design_context, verified_files, spec)

        # Generate
        try:
            output = await _generate_unit(spec, context, settings=settings)
        except Exception as exc:
            logger.warning(
                "atomic_generation.unit_failed",
                unit=spec.name,
                error=str(exc)[:200],
            )
            progress.failed.append(
                AtomicUnitResult(
                    spec=spec,
                    output=AtomicScaffoldUnit(),  # empty placeholder
                    verified=False,
                    verification_errors=[str(exc)[:200]],
                )
            )
            continue

        # Verify and fix
        unit_result = AtomicUnitResult(spec=spec, output=output)
        unit_result = await verify_and_fix_unit(
            unit_result, verified_files, settings=settings, max_fix_attempts=max_fixes
        )

        # Accumulate
        progress.add_result(unit_result)
        if unit_result.verified:
            verified_files.extend(unit_result.output.files)

        logger.info(
            "atomic_generation.unit_complete",
            unit=spec.name,
            verified=unit_result.verified,
            files=len(unit_result.output.files),
            fix_attempts=unit_result.fix_attempts,
        )

    logger.info(
        "atomic_generation.complete",
        completed=len(progress.completed),
        failed=len(progress.failed),
        total_files=len(progress.all_files),
    )
    return progress
