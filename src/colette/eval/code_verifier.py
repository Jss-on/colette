"""Deterministic syntax/import/type checks.

Replaces ``VerificationReport`` from LLM verifier
(``lint_passed``, ``type_check_passed``, ``build_passed``).
"""

from __future__ import annotations

import ast
import sys
from typing import NamedTuple

from colette.eval._ast_helpers import (
    check_balanced_delimiters,
    parse_python_functions,
)

# ── Data types ───────────────────────────────────────────────────────


class VerificationFinding(NamedTuple):
    category: str  # "syntax" | "import" | "type" | "structure"
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    file_path: str
    line: int | None
    message: str


class DeterministicVerificationReport(NamedTuple):
    findings: tuple[VerificationFinding, ...]
    lint_passed: bool  # no syntax errors
    type_check_passed: bool  # all public functions have type annotations
    build_passed: bool  # all imports resolve


# ── Known packages ───────────────────────────────────────────────────

KNOWN_PACKAGES = frozenset(
    {
        "fastapi",
        "pydantic",
        "sqlalchemy",
        "alembic",
        "pytest",
        "httpx",
        "uvicorn",
        "redis",
        "celery",
        "jwt",
        "bcrypt",
        "passlib",
        "react",
        "next",
        "express",
        "prisma",
        "zod",
        "axios",
        "jest",
        "tailwindcss",
        "lucide-react",
        "shadcn",
    }
)

# ── Check functions ──────────────────────────────────────────────────


def _check_syntax(file_path: str, content: str) -> list[VerificationFinding]:
    """Check syntax validity."""
    findings: list[VerificationFinding] = []

    if file_path.endswith(".py"):
        try:
            ast.parse(content)
        except SyntaxError as e:
            findings.append(
                VerificationFinding(
                    category="syntax",
                    severity="CRITICAL",
                    file_path=file_path,
                    line=e.lineno,
                    message=f"Python syntax error: {e.msg}",
                )
            )
    elif file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
        errors = check_balanced_delimiters(content)
        for error in errors:
            findings.append(
                VerificationFinding(
                    category="syntax",
                    severity="CRITICAL",
                    file_path=file_path,
                    line=None,
                    message=f"Delimiter error: {error}",
                )
            )

    return findings


def _is_stdlib_module(module: str) -> bool:
    """Check if a module is in the Python standard library."""
    top = module.split(".")[0]
    return top in sys.stdlib_module_names


def _check_imports(
    file_path: str,
    content: str,
    all_files: dict[str, str],
) -> list[VerificationFinding]:
    """Check that imports resolve to known modules."""
    if not file_path.endswith(".py"):
        return []

    findings: list[VerificationFinding] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    generated_modules: set[str] = set()
    for fp in all_files:
        if fp.endswith(".py"):
            # Convert file path to module path
            parts = fp.replace("\\", "/").replace("/", ".").removesuffix(".py")
            generated_modules.add(parts)
            # Also add top-level package
            top = parts.split(".")[0]
            generated_modules.add(top)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if not _is_known_module(module, generated_modules):
                    findings.append(
                        VerificationFinding(
                            category="import",
                            severity="HIGH",
                            file_path=file_path,
                            line=node.lineno,
                            message=f"Unknown import: '{alias.name}'",
                        )
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split(".")[0]
            if not _is_known_module(module, generated_modules):
                findings.append(
                    VerificationFinding(
                        category="import",
                        severity="HIGH",
                        file_path=file_path,
                        line=node.lineno,
                        message=f"Unknown import: 'from {node.module}'",
                    )
                )

    return findings


def _is_known_module(module: str, generated_modules: set[str]) -> bool:
    """Check if a module is stdlib, known third-party, or in generated files."""
    return _is_stdlib_module(module) or module in KNOWN_PACKAGES or module in generated_modules


def _check_type_annotations(file_path: str, content: str) -> list[VerificationFinding]:
    """Check that public functions have return type annotations."""
    if not file_path.endswith(".py"):
        return []

    findings: list[VerificationFinding] = []
    funcs = parse_python_functions(content)

    for func in funcs:
        if func.is_private:
            continue
        if not func.has_return_annotation:
            findings.append(
                VerificationFinding(
                    category="type",
                    severity="MEDIUM",
                    file_path=file_path,
                    line=func.line,
                    message=f"Public function '{func.name}' missing return type annotation",
                )
            )

    return findings


def _check_package_structure(
    all_files: dict[str, str],
) -> list[VerificationFinding]:
    """Verify ``__init__.py`` exists for packages implied by imports."""
    findings: list[VerificationFinding] = []
    py_files = {fp for fp in all_files if fp.endswith(".py")}
    dirs_with_py: set[str] = set()

    for fp in py_files:
        normalized = fp.replace("\\", "/")
        parts = normalized.rsplit("/", 1)
        if len(parts) == 2:
            dirs_with_py.add(parts[0])

    for directory in dirs_with_py:
        init_path = f"{directory}/__init__.py"
        if init_path not in py_files:
            # Check with backslash variant too
            init_path_win = init_path.replace("/", "\\")
            if init_path_win not in py_files:
                findings.append(
                    VerificationFinding(
                        category="structure",
                        severity="MEDIUM",
                        file_path=init_path,
                        line=None,
                        message=f"Missing __init__.py for package '{directory}'",
                    )
                )

    return findings


# ── Main entry ───────────────────────────────────────────────────────


def verify_files(
    files: list[dict[str, str]],
) -> DeterministicVerificationReport:
    """Run all deterministic verification checks on generated files."""
    all_files: dict[str, str] = {}
    for f in files:
        all_files[f.get("path", "")] = f.get("content", "")

    all_findings: list[VerificationFinding] = []

    for file_path, content in all_files.items():
        all_findings.extend(_check_syntax(file_path, content))
        all_findings.extend(_check_imports(file_path, content, all_files))
        all_findings.extend(_check_type_annotations(file_path, content))

    all_findings.extend(_check_package_structure(all_files))

    findings_tuple = tuple(all_findings)

    lint_passed = not any(f.category == "syntax" for f in findings_tuple)
    type_check_passed = not any(f.category == "type" for f in findings_tuple)
    build_passed = not any(f.category == "import" for f in findings_tuple)

    return DeterministicVerificationReport(
        findings=findings_tuple,
        lint_passed=lint_passed,
        type_check_passed=type_check_passed,
        build_passed=build_passed,
    )
