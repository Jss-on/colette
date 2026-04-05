"""Tests for colette.eval._ast_helpers."""

from __future__ import annotations

from colette.eval._ast_helpers import (
    check_balanced_delimiters,
    count_python_branches,
    count_python_branches_per_function,
    extract_exported_names,
    extract_ts_functions,
    extract_ts_imports,
    parse_python_classes,
    parse_python_functions,
    parse_python_imports,
)

# ── parse_python_functions ───────────────────────────────────────────


class TestParsePythonFunctions:
    def test_single_function(self) -> None:
        code = "def foo(x: int) -> str:\n    return str(x)\n"
        funcs = parse_python_functions(code)
        assert len(funcs) == 1
        assert funcs[0].name == "foo"
        assert funcs[0].args == ("x",)
        assert funcs[0].has_return_annotation is True
        assert funcs[0].is_method is False
        assert funcs[0].is_private is False

    def test_private_function(self) -> None:
        code = "def _helper():\n    pass\n"
        funcs = parse_python_functions(code)
        assert len(funcs) == 1
        assert funcs[0].is_private is True

    def test_class_method(self) -> None:
        code = "class MyClass:\n    def my_method(self, x: int) -> None:\n        pass\n"
        funcs = parse_python_functions(code)
        assert len(funcs) == 1
        assert funcs[0].name == "my_method"
        assert funcs[0].is_method is True
        assert funcs[0].args == ("x",)

    def test_async_function(self) -> None:
        code = "async def fetch_data(url: str) -> dict:\n    pass\n"
        funcs = parse_python_functions(code)
        assert len(funcs) == 1
        assert funcs[0].name == "fetch_data"

    def test_malformed_python_returns_empty(self) -> None:
        code = "def foo(:\n"
        funcs = parse_python_functions(code)
        assert funcs == []

    def test_no_return_annotation(self) -> None:
        code = "def bar(x):\n    pass\n"
        funcs = parse_python_functions(code)
        assert funcs[0].has_return_annotation is False


# ── parse_python_imports ─────────────────────────────────────────────


class TestParsePythonImports:
    def test_import_statement(self) -> None:
        code = "import os\n"
        imports = parse_python_imports(code)
        assert len(imports) == 1
        assert imports[0].module == "os"

    def test_from_import(self) -> None:
        code = "from pathlib import Path, PurePath\n"
        imports = parse_python_imports(code)
        assert len(imports) == 1
        assert imports[0].module == "pathlib"
        assert imports[0].names == ("Path", "PurePath")

    def test_malformed_returns_empty(self) -> None:
        code = "from import oops\n"
        imports = parse_python_imports(code)
        assert imports == []


# ── parse_python_classes ─────────────────────────────────────────────


class TestParsePythonClasses:
    def test_class_with_method(self) -> None:
        code = (
            "class User:\n"
            "    name: str\n"
            "    email: str\n"
            "\n"
            "    def greet(self) -> str:\n"
            "        return f'Hi {self.name}'\n"
        )
        classes = parse_python_classes(code)
        assert len(classes) == 1
        assert classes[0].name == "User"
        assert "name" in classes[0].field_names
        assert "email" in classes[0].field_names
        assert classes[0].methods == ("greet",)

    def test_class_with_bases(self) -> None:
        code = "class Admin(User, Mixin):\n    pass\n"
        classes = parse_python_classes(code)
        assert classes[0].bases == ("User", "Mixin")

    def test_malformed_returns_empty(self) -> None:
        code = "class {bad:\n"
        classes = parse_python_classes(code)
        assert classes == []


# ── count_python_branches ────────────────────────────────────────────


class TestCountPythonBranches:
    def test_if_elif_else(self) -> None:
        code = (
            "def f(x):\n"
            "    if x > 0:\n"
            "        pass\n"
            "    elif x == 0:\n"
            "        pass\n"
            "    else:\n"
            "        pass\n"
        )
        # if + elif = 2 branches (else is not a branch point)
        assert count_python_branches(code) == 2

    def test_for_while_except(self) -> None:
        code = (
            "for i in range(10):\n"
            "    try:\n"
            "        while True:\n"
            "            break\n"
            "    except ValueError:\n"
            "        pass\n"
        )
        # for + while + except = 3
        assert count_python_branches(code) == 3

    def test_ternary(self) -> None:
        code = "x = 1 if True else 0\n"
        assert count_python_branches(code) == 1

    def test_malformed_returns_zero(self) -> None:
        assert count_python_branches("def (broken:") == 0


# ── count_python_branches_per_function ───────────────────────────────


class TestCountPythonBranchesPerFunction:
    def test_per_function(self) -> None:
        code = (
            "def simple():\n"
            "    pass\n"
            "\n"
            "def complex_func(x):\n"
            "    if x > 0:\n"
            "        for i in range(x):\n"
            "            pass\n"
        )
        result = count_python_branches_per_function(code)
        assert result["simple"] == 0
        assert result["complex_func"] == 2


# ── extract_ts_functions ─────────────────────────────────────────────


class TestExtractTsFunctions:
    def test_export_function(self) -> None:
        code = "export function getUser(id: string) {\n  return id;\n}\n"
        names = extract_ts_functions(code)
        assert "getUser" in names

    def test_arrow_function(self) -> None:
        code = "const fetchData = async (url: string) => {\n  return url;\n};\n"
        names = extract_ts_functions(code)
        assert "fetchData" in names

    def test_export_async_function(self) -> None:
        code = "export async function loadItems() {\n  return [];\n}\n"
        names = extract_ts_functions(code)
        assert "loadItems" in names

    def test_keywords_excluded(self) -> None:
        code = "if (true) {\n  return;\n}\n"
        names = extract_ts_functions(code)
        assert "if" not in names


# ── extract_ts_imports ───────────────────────────────────────────────


class TestExtractTsImports:
    def test_es_import(self) -> None:
        code = "import { useState } from 'react';\n"
        imports = extract_ts_imports(code)
        assert "react" in imports

    def test_require(self) -> None:
        code = "const express = require('express');\n"
        imports = extract_ts_imports(code)
        assert "express" in imports


# ── check_balanced_delimiters ────────────────────────────────────────


class TestCheckBalancedDelimiters:
    def test_balanced(self) -> None:
        code = "function foo() {\n  if (x) {\n    return [1, 2];\n  }\n}\n"
        errors = check_balanced_delimiters(code)
        assert errors == []

    def test_unbalanced_brace(self) -> None:
        code = "function foo() {\n  if (x) {\n    return 1;\n}\n"
        errors = check_balanced_delimiters(code)
        assert len(errors) > 0

    def test_unbalanced_paren(self) -> None:
        code = "console.log(('hello')\n"
        errors = check_balanced_delimiters(code)
        assert len(errors) > 0


# ── extract_exported_names ───────────────────────────────────────────


class TestExtractExportedNames:
    def test_all_list(self) -> None:
        code = '__all__ = ["foo", "bar", "baz"]\n'
        names = extract_exported_names(code)
        assert names == {"foo", "bar", "baz"}

    def test_all_tuple(self) -> None:
        code = "__all__ = ('alpha', 'beta')\n"
        names = extract_exported_names(code)
        assert names == {"alpha", "beta"}

    def test_no_all(self) -> None:
        code = "x = 1\n"
        names = extract_exported_names(code)
        assert names == set()

    def test_malformed_returns_empty(self) -> None:
        code = "__all__ = [oops broken\n"
        names = extract_exported_names(code)
        assert names == set()
