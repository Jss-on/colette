"""Shared AST parsing utilities used by all deterministic evaluators.

Python files are parsed via ``ast``; TypeScript/JavaScript files use regex.
"""

from __future__ import annotations

import ast
import re
from typing import NamedTuple

# ── Data types ───────────────────────────────────────────────────────


class FunctionInfo(NamedTuple):
    name: str
    args: tuple[str, ...]
    has_return_annotation: bool
    line: int
    is_method: bool
    is_private: bool


class ImportInfo(NamedTuple):
    module: str
    names: tuple[str, ...]
    line: int


class ClassInfo(NamedTuple):
    name: str
    bases: tuple[str, ...]
    field_names: frozenset[str]
    methods: tuple[str, ...]


# ── Python helpers (ast-based) ───────────────────────────────────────


def parse_python_functions(content: str) -> list[FunctionInfo]:
    """Parse Python source and return function/method information."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    results: list[FunctionInfo] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Determine if this is a method by checking parent context
            is_method = _is_method(tree, node)
            args = tuple(
                arg.arg for arg in node.args.args if arg.arg != "self" and arg.arg != "cls"
            )
            results.append(
                FunctionInfo(
                    name=node.name,
                    args=args,
                    has_return_annotation=node.returns is not None,
                    line=node.lineno,
                    is_method=is_method,
                    is_private=node.name.startswith("_"),
                )
            )

    return results


def _is_method(tree: ast.Module, func_node: ast.AST) -> bool:
    """Check whether *func_node* is directly inside a ClassDef."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if child is func_node:
                    return True
    return False


def parse_python_imports(content: str) -> list[ImportInfo]:
    """Parse Python source and return import information."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    results: list[ImportInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                results.append(
                    ImportInfo(
                        module=alias.name,
                        names=(alias.asname or alias.name,),
                        line=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = tuple(alias.name for alias in node.names)
            results.append(ImportInfo(module=module, names=names, line=node.lineno))

    return results


def parse_python_classes(content: str) -> list[ClassInfo]:
    """Parse Python source and return class information."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    results: list[ClassInfo] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = tuple(_get_name(base) for base in node.bases)
            field_names: set[str] = set()
            methods: list[str] = []

            for child in node.body:
                if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                    field_names.add(child.target.id)
                elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                    methods.append(child.name)

            results.append(
                ClassInfo(
                    name=node.name,
                    bases=bases,
                    field_names=frozenset(field_names),
                    methods=tuple(methods),
                )
            )

    return results


def _get_name(node: ast.expr) -> str:
    """Extract a human-readable name from an AST expression node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_get_name(node.value)}.{node.attr}"
    return "<unknown>"


def count_python_branches(content: str) -> int:
    """Count branch points (if/elif/for/while/except/ternary) in Python source."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return 0

    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.If | ast.For | ast.While | ast.ExceptHandler | ast.IfExp):
            count += 1
    return count


def count_python_branches_per_function(content: str) -> dict[str, int]:
    """Map of function name to branch count within that function."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}

    result: dict[str, int] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            count = 0
            for child in ast.walk(node):
                if child is node:
                    continue
                if isinstance(child, ast.If | ast.For | ast.While | ast.ExceptHandler | ast.IfExp):
                    count += 1
            result[node.name] = count

    return result


# ── TypeScript/JavaScript helpers (regex-based) ──────────────────────

_TS_FUNC_PATTERNS = [
    re.compile(r"export\s+(?:async\s+)?function\s+(\w+)"),
    re.compile(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(.*?\)\s*=>"),
    re.compile(r"(\w+)\s*\(.*?\)\s*\{"),
]


def extract_ts_functions(content: str) -> list[str]:
    """Extract TypeScript/JavaScript function names via regex."""
    names: list[str] = []
    seen: set[str] = set()

    for pattern in _TS_FUNC_PATTERNS:
        for match in pattern.finditer(content):
            name = match.group(1)
            if name not in seen and name not in _TS_KEYWORDS:
                seen.add(name)
                names.append(name)

    return names


_TS_KEYWORDS = frozenset(
    {
        "if",
        "else",
        "for",
        "while",
        "switch",
        "case",
        "return",
        "class",
        "function",
        "import",
        "export",
        "default",
        "new",
        "try",
        "catch",
        "finally",
        "throw",
        "typeof",
        "instanceof",
    }
)

_TS_IMPORT_PATTERNS = [
    re.compile(r"""import\s+.*?\s+from\s+['"](.+?)['"]"""),
    re.compile(r"""require\s*\(\s*['"](.+?)['"]\s*\)"""),
]


def extract_ts_imports(content: str) -> list[str]:
    """Extract TypeScript/JavaScript import sources via regex."""
    imports: list[str] = []
    seen: set[str] = set()

    for pattern in _TS_IMPORT_PATTERNS:
        for match in pattern.finditer(content):
            source = match.group(1)
            if source not in seen:
                seen.add(source)
                imports.append(source)

    return imports


# ── Shared helpers ───────────────────────────────────────────────────


def check_balanced_delimiters(content: str) -> list[str]:
    """Check ``{}``, ``[]``, ``()`` balance. Returns list of errors."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    closers = set(pairs.values())
    stack: list[tuple[str, int]] = []
    errors: list[str] = []

    for lineno, line in enumerate(content.splitlines(), 1):
        in_string = False
        string_char = ""
        i = 0
        while i < len(line):
            ch = line[i]

            # Skip escaped characters inside strings
            if in_string:
                if ch == "\\" and i + 1 < len(line):
                    i += 2
                    continue
                if ch == string_char:
                    in_string = False
                i += 1
                continue

            if ch in ('"', "'", "`"):
                in_string = True
                string_char = ch
                i += 1
                continue

            # Skip single-line comments
            if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            if ch == "#":
                break

            if ch in pairs:
                stack.append((ch, lineno))
            elif ch in closers:
                if not stack:
                    errors.append(f"Unmatched '{ch}' at line {lineno}")
                else:
                    top, _ = stack[-1]
                    if pairs[top] == ch:
                        stack.pop()
                    else:
                        errors.append(f"Mismatched '{top}' and '{ch}' at line {lineno}")
                        stack.pop()

            i += 1

    for opener, lineno in stack:
        errors.append(f"Unclosed '{opener}' opened at line {lineno}")

    return errors


def extract_exported_names(content: str) -> set[str]:
    """Extract Python ``__all__`` exported names."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, ast.List | ast.Tuple)
                ):
                    return {
                        elt.value
                        for elt in node.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    }
    return set()
