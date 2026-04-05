"""Tests for colette.eval.code_verifier."""

from __future__ import annotations

from colette.eval.code_verifier import verify_files


def _file(content: str, path: str = "app.py") -> dict[str, str]:
    return {"path": path, "content": content}


class TestVerifyFiles:
    def test_valid_python(self) -> None:
        files = [_file("def foo() -> int:\n    return 1\n")]
        report = verify_files(files)
        assert report.lint_passed is True

    def test_syntax_error(self) -> None:
        files = [_file("def foo(:\n")]
        report = verify_files(files)
        assert report.lint_passed is False
        syntax_findings = [f for f in report.findings if f.category == "syntax"]
        assert len(syntax_findings) >= 1

    def test_valid_imports_in_generated_set(self) -> None:
        files = [
            _file("import os\nfrom myapp import helper\n", "main.py"),
            _file("def helper() -> None: pass\n", "myapp.py"),
        ]
        report = verify_files(files)
        assert report.build_passed is True

    def test_missing_import(self) -> None:
        files = [_file("import totally_unknown_package\n")]
        report = verify_files(files)
        assert report.build_passed is False

    def test_stdlib_import_ok(self) -> None:
        files = [_file("import os\nimport json\nimport pathlib\n")]
        report = verify_files(files)
        import_findings = [f for f in report.findings if f.category == "import"]
        assert len(import_findings) == 0

    def test_missing_return_type(self) -> None:
        files = [_file("def public_func(x):\n    return x\n")]
        report = verify_files(files)
        assert report.type_check_passed is False

    def test_private_function_no_annotation_ok(self) -> None:
        files = [_file("def _private(x):\n    return x\n")]
        report = verify_files(files)
        type_findings = [f for f in report.findings if f.category == "type"]
        assert len(type_findings) == 0

    def test_missing_init_py(self) -> None:
        files = [_file("x = 1\n", "mypackage/module.py")]
        report = verify_files(files)
        structure_findings = [f for f in report.findings if f.category == "structure"]
        assert len(structure_findings) >= 1

    def test_ts_unbalanced_braces(self) -> None:
        files = [_file("function foo() {\n  if (x) {\n    return 1;\n}\n", "app.ts")]
        report = verify_files(files)
        assert report.lint_passed is False

    def test_ts_balanced_passes(self) -> None:
        files = [
            _file(
                "function foo() {\n  if (x) {\n    return 1;\n  }\n}\n",
                "app.ts",
            )
        ]
        report = verify_files(files)
        assert report.lint_passed is True

    def test_known_package_ok(self) -> None:
        files = [_file("import fastapi\nimport pydantic\n")]
        report = verify_files(files)
        assert report.build_passed is True
