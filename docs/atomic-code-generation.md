# Atomic Code Generation

## Context

Currently each implementation agent (frontend, backend, database) generates ALL files in one massive LLM call. This is unreliable (truncation, all-or-nothing errors) and unlike how real developers work. The `docs/deterministic-eval/` framework already applies "atomic per-endpoint/function/pattern" to *evaluation*. This plan applies the same principle to *generation*: one entity, one endpoint, one component at a time, verified incrementally.

## What Changes

### New Files

1. **`src/colette/schemas/atomic.py`** — Data structures for atomic units
   - `AtomicUnitKind(StrEnum)`: SCAFFOLDING, DATABASE_ENTITY, BACKEND_ENDPOINT, FRONTEND_COMPONENT
   - `AtomicUnitSpec(BaseModel, frozen=True)`: kind, name, entity_spec/endpoint_spec/component_spec (optional), depends_on, phase (0-3)
   - Per-unit output models: `AtomicScaffoldUnit`, `AtomicDatabaseUnit`, `AtomicBackendUnit`, `AtomicFrontendUnit` — each has `files: list[GeneratedFile]`, `packages: list[str]`, `env_vars: list[str]`, `notes: str`
   - `AtomicUnitResult(BaseModel)`: wraps generation output + verification status (verified, verification_errors, fix_attempts)
   - `AtomicGenerationProgress(BaseModel)`: accumulator across all units

2. **`src/colette/stages/implementation/atomic.py`** (~400 lines) — Core orchestration
   - `extract_atomic_units(handoff, module_design) -> list[AtomicUnitSpec]`: Extracts units from `DesignToImplementationHandoff.db_entities`, `.endpoints`, `.ui_components`; uses `EntitySpec.relationships` for FK deps, `EndpointSpec.auth_required` for ordering, `ComponentSpec.children` for leaf-first ordering
   - `topological_sort_units(units) -> list[AtomicUnitSpec]`: Uses `graphlib.TopologicalSorter` (stdlib); secondary sort by phase then name
   - `build_incremental_context(design_context, verified_files, current_spec, *, max_context_chars=60000) -> str`: Tiered context — same-domain files get full content, adjacent-domain get signatures only, distant get paths only
   - `generate_scaffolding()`, `generate_database_entity()`, `generate_backend_endpoint()`, `generate_frontend_component()`: Each calls `invoke_structured()` with focused prompt + small output model
   - `verify_and_fix_unit(unit_result, all_prior_files, *, settings, max_fix_attempts=2) -> AtomicUnitResult`: Deterministic eval if available (graceful import fallback), else LLM-based verification filtered to unit's file paths
   - `run_atomic_generation(handoff, design_context, module_design, *, settings) -> AtomicGenerationProgress`: Main loop — extract -> sort -> generate each unit sequentially -> verify -> accumulate

3. **`tests/unit/stages/implementation/test_atomic.py`** — Tests for all atomic functions

### Modified Files

4. **`src/colette/config.py`** (after line 136) — Add two settings:
   - `use_atomic_generation: bool = False`
   - `atomic_max_fix_attempts: int = 2`

5. **`src/colette/stages/implementation/prompts.py`** (append) — Four focused prompts:
   - `ATOMIC_SCAFFOLDING_PROMPT`, `ATOMIC_DATABASE_ENTITY_PROMPT`, `ATOMIC_BACKEND_ENDPOINT_PROMPT`, `ATOMIC_FRONTEND_COMPONENT_PROMPT`
   - Each reuses existing `_IMPLEMENTATION_RULES` and adds: "Previously generated files are provided for context. Import them; do NOT regenerate them."

6. **`src/colette/stages/implementation/verifier.py`** — Add `filter_findings_to_paths(report, paths) -> VerificationReport` (~15 lines)

7. **`src/colette/stages/implementation/supervisor.py`** — Feature flag branch in `supervise_implementation()`:
   - After Step 2 (test agent, line 365), insert: `if settings.use_atomic_generation: return await _run_atomic_path(...)`
   - New `_run_atomic_path()`: calls `run_atomic_generation()` -> converts progress to `FrontendResult`/`BackendResult`/`DatabaseResult` -> runs refactor + cross-review -> calls existing `assemble_handoff()`
   - New `_progress_to_agent_results()`: classifies atomic unit files by kind into the three result types
   - Existing bulk path (Steps 3-6) unchanged in `else` branch

### NOT Modified

- `frontend.py`, `backend.py`, `database.py` — bulk fallback, untouched
- `architect_agent.py`, `test_agent.py` — run identically in both paths
- `stage.py` — calls `supervise_implementation()` which handles branching
- All handoff schemas — atomic path converts to existing types at supervisor boundary
- All gates — consume same handoff fields

## Generation Order

Mirrors how a real software developer builds a project:

```
Phase 0: Scaffolding (config, package.json, pyproject.toml)
Phase 1: Database entities (FK-ordered: referenced tables before referencing)
Phase 2: Backend endpoints (auth endpoints first, then protected routes)
Phase 3: Frontend components (leaf components before pages that compose them)
```

Each unit is verified immediately after generation. Prior verified files feed into the next unit's context as incremental knowledge.

### Incremental Context Strategy

When generating each atomic unit, the LLM receives tiered context from previously verified files:

| Tier | Content Level | Example |
|------|--------------|---------|
| Tier 1 (same domain) | Full file content | Backend endpoint gets all prior backend files |
| Tier 2 (adjacent domain) | Signatures only | Backend endpoint gets DB model class/field signatures |
| Tier 3 (distant domain) | File paths only | DB entity gets frontend file paths |

Truncation priority: drop Tier 3 first, then Tier 2 (oldest first), then Tier 1 (oldest first). Never truncate the current unit spec.

## Integration with Deterministic Eval

After each atomic unit, the following deterministic checks run:

| Unit Type | Checks Applied |
|-----------|---------------|
| All units | `code_verifier.verify_files()` — syntax, imports, types |
| Backend endpoints | `contract_checker.check_contracts()` — OpenAPI spec match |
| Frontend components | `cross_review_checker.check_cross_review()` — API call match |
| Database entities | Structure verification — entity matches design spec |

If deterministic eval module (`src/colette/eval/`) is not yet available, falls back gracefully to LLM-based verification filtered to the unit's file paths.

## Implementation Sequence

| Step | File | Depends On |
|------|------|-----------|
| 1 | `src/colette/schemas/atomic.py` | -- |
| 2 | `src/colette/stages/implementation/prompts.py` | -- |
| 3 | `src/colette/stages/implementation/verifier.py` | -- |
| 4 | `src/colette/config.py` | -- |
| 5 | `src/colette/stages/implementation/atomic.py` | Steps 1-4 |
| 6 | `src/colette/stages/implementation/supervisor.py` | Step 5 |
| 7 | `tests/unit/stages/implementation/test_atomic.py` | Step 6 |

Steps 1-4 are independent (can be implemented in parallel). Step 5 depends on all four. Steps 6-7 are sequential after Step 5.

## Feature Flag

Controlled via `COLETTE_USE_ATOMIC_GENERATION` environment variable (default: `false`). When disabled, the existing bulk generation path runs unchanged. This follows the same pattern as `use_deterministic_eval` proposed in `docs/deterministic-eval/07-integration-plan.md`.

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| More total LLM calls = higher cost | Each call is smaller + more reliable + fewer retries. Net cost comparable. |
| Sequential generation slower than parallel bulk | Independent units within same phase can use `asyncio.gather`. First optimization after basic loop works. |
| Deterministic eval not yet implemented | Graceful import fallback to LLM-based verification. |
| Feature flag creates two code paths | Standard pattern. Remove bulk path once atomic is proven. |
| Existing tests break | All changes additive. Flag defaults false. No existing code modified except additive insertions. |

## Verification

```bash
make lint                     # ruff check passes
make typecheck                # mypy passes
make test-unit                # all tests pass, 80%+ coverage
uv run pytest tests/unit/stages/implementation/test_atomic.py -v  # new tests pass
# Manual: run with COLETTE_USE_ATOMIC_GENERATION=true on a sample project
```
