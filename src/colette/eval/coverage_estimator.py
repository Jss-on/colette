"""AST-based test coverage estimation.

Replaces ``UnitTestResult.estimated_line_coverage`` +
``estimated_branch_coverage`` with structural analysis.
"""

from __future__ import annotations

from typing import NamedTuple

from colette.eval._ast_helpers import (
    count_python_branches_per_function,
    parse_python_functions,
)

# ── Data types ───────────────────────────────────────────────────────


class CoverageEstimate(NamedTuple):
    line_coverage: float  # 0.0 - 100.0
    branch_coverage: float  # 0.0 - 100.0
    functions_total: int
    functions_covered: int
    branches_total: int
    branches_covered: int


# ── Internal helpers ─────────────────────────────────────────────────


def _extract_source_functions(
    source_files: list[dict[str, str]],
) -> dict[str, list[str]]:
    """Parse non-test files, extract function/method names per file."""
    result: dict[str, list[str]] = {}
    for f in source_files:
        path = f.get("path", "")
        content = f.get("content", "")
        funcs = parse_python_functions(content)
        names = [fn.name for fn in funcs if not fn.name.startswith("test_")]
        if names:
            result[path] = names
    return result


def _extract_test_references(
    test_files: list[dict[str, str]],
) -> set[str]:
    """Parse test files, collect all referenced names."""
    references: set[str] = set()
    for f in test_files:
        content = f.get("content", "")
        # Collect all identifiers that appear in test files
        # This catches imports, function calls, assertions, etc.
        import re

        for match in re.finditer(r"\b(\w+)\b", content):
            references.add(match.group(1))
    return references


def _count_branches_in_functions(
    source_files: list[dict[str, str]],
    covered_funcs: set[str],
) -> tuple[int, int]:
    """Count branches total vs branches in covered functions."""
    total = 0
    covered = 0
    for f in source_files:
        content = f.get("content", "")
        branches_map = count_python_branches_per_function(content)
        for func_name, branch_count in branches_map.items():
            if func_name.startswith("test_"):
                continue
            total += branch_count
            if func_name in covered_funcs:
                covered += branch_count
    return total, covered


# ── Main entry ───────────────────────────────────────────────────────


def estimate_coverage(
    source_files: list[dict[str, str]],
    test_files: list[dict[str, str]],
    *,
    boost_multiplier: float = 1.15,
) -> CoverageEstimate:
    """Estimate test coverage from source and test file ASTs.

    Line coverage = covered funcs / total funcs * 100.
    Branch coverage = branches in covered funcs / total branches * 100.
    Both are multiplied by *boost_multiplier* and capped at 100.
    """
    source_funcs = _extract_source_functions(source_files)
    all_func_names: list[str] = []
    for names in source_funcs.values():
        all_func_names.extend(names)

    if not all_func_names:
        return CoverageEstimate(
            line_coverage=100.0,
            branch_coverage=100.0,
            functions_total=0,
            functions_covered=0,
            branches_total=0,
            branches_covered=0,
        )

    if not test_files:
        return CoverageEstimate(
            line_coverage=0.0,
            branch_coverage=0.0,
            functions_total=len(all_func_names),
            functions_covered=0,
            branches_total=0,
            branches_covered=0,
        )

    test_refs = _extract_test_references(test_files)
    covered_funcs = {name for name in all_func_names if name in test_refs}

    functions_total = len(all_func_names)
    functions_covered = len(covered_funcs)

    branches_total, branches_covered = _count_branches_in_functions(source_files, covered_funcs)

    raw_line = (functions_covered / functions_total) * 100.0
    line_coverage = min(100.0, raw_line * boost_multiplier)

    if branches_total == 0:
        branch_coverage = line_coverage
    else:
        raw_branch = (branches_covered / branches_total) * 100.0
        branch_coverage = min(100.0, raw_branch * boost_multiplier)

    return CoverageEstimate(
        line_coverage=round(line_coverage, 2),
        branch_coverage=round(branch_coverage, 2),
        functions_total=functions_total,
        functions_covered=functions_covered,
        branches_total=branches_total,
        branches_covered=branches_covered,
    )
