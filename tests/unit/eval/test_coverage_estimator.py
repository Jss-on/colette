"""Tests for colette.eval.coverage_estimator."""

from __future__ import annotations

from colette.eval.coverage_estimator import estimate_coverage


def _src(content: str, path: str = "app.py") -> dict[str, str]:
    return {"path": path, "content": content}


def _test(content: str, path: str = "test_app.py") -> dict[str, str]:
    return {"path": path, "content": content}


class TestEstimateCoverage:
    def test_full_coverage(self) -> None:
        source = [
            _src(
                "def get_user(): pass\n"
                "def create_user(): pass\n"
                "def delete_user(): pass\n"
                "def update_user(): pass\n"
                "def list_users(): pass\n"
            )
        ]
        tests = [
            _test(
                "from app import get_user, create_user, delete_user, update_user, list_users\n"
                "def test_get(): get_user()\n"
                "def test_create(): create_user()\n"
                "def test_delete(): delete_user()\n"
                "def test_update(): update_user()\n"
                "def test_list(): list_users()\n"
            )
        ]
        result = estimate_coverage(source, tests)
        assert result.line_coverage >= 95.0
        assert result.functions_total == 5
        assert result.functions_covered == 5

    def test_partial_coverage(self) -> None:
        source = [
            _src(
                "def get_user(): pass\n"
                "def create_user(): pass\n"
                "def delete_user(): pass\n"
                "def update_user(): pass\n"
                "def list_users(): pass\n"
            )
        ]
        tests = [
            _test(
                "from app import get_user, create_user, delete_user\ndef test_get(): get_user()\n"
            )
        ]
        result = estimate_coverage(source, tests)
        # 3 out of 5 = 60% * 1.15 = 69%
        assert 60.0 <= result.line_coverage <= 75.0
        assert result.functions_covered == 3

    def test_no_test_files(self) -> None:
        source = [_src("def foo(): pass\n")]
        result = estimate_coverage(source, [])
        assert result.line_coverage == 0.0
        assert result.branch_coverage == 0.0

    def test_no_source_functions(self) -> None:
        source = [_src("# just a config file\nX = 1\n")]
        result = estimate_coverage(source, [_test("pass\n")])
        assert result.line_coverage == 100.0

    def test_branch_coverage(self) -> None:
        source = [
            _src(
                "def check(x: int) -> str:\n"
                "    if x > 0:\n"
                "        return 'pos'\n"
                "    elif x == 0:\n"
                "        return 'zero'\n"
                "    return 'neg'\n"
                "\n"
                "def simple() -> int:\n"
                "    return 1\n"
            )
        ]
        tests = [_test("from app import check\ndef test_check(): check(1)\n")]
        result = estimate_coverage(source, tests)
        assert result.branches_total >= 2
        assert result.branches_covered >= 2

    def test_wrong_name_not_covered(self) -> None:
        source = [_src("def get_user(): pass\n")]
        tests = [_test("def test_it(): get_users()\n")]  # note: get_users != get_user
        result = estimate_coverage(source, tests)
        assert result.functions_covered == 0

    def test_test_functions_excluded_from_source(self) -> None:
        source = [_src("def real_func(): pass\ndef test_something(): pass\n")]
        tests = [_test("from app import real_func\ndef test_it(): real_func()\n")]
        result = estimate_coverage(source, tests)
        assert result.functions_total == 1
