"""Tests for colette.eval.cross_review_checker."""

from __future__ import annotations

from colette.eval.cross_review_checker import (
    _normalize_field_name,
    check_cross_review,
)


def _fe(content: str, path: str = "app.tsx") -> dict[str, str]:
    return {"path": path, "content": content}


def _be(content: str, path: str = "app.py") -> dict[str, str]:
    return {"path": path, "content": content}


class TestCheckCrossReview:
    def test_matching_endpoints(self) -> None:
        fe = [_fe('const data = await fetch("/api/todos");\n')]
        be = [_be('@app.get("/api/todos")\nasync def list_todos(): pass\n')]
        report = check_cross_review(fe, be)
        critical = [f for f in report.findings if f.severity == "CRITICAL"]
        assert len(critical) == 0

    def test_missing_backend(self) -> None:
        fe = [_fe('const data = await fetch("/api/missing");\n')]
        be = [_be('@app.get("/api/todos")\nasync def list_todos(): pass\n')]
        report = check_cross_review(fe, be)
        assert report.has_critical is True
        missing = [f for f in report.findings if f.category == "missing_backend_endpoint"]
        assert len(missing) >= 1

    def test_unused_backend(self) -> None:
        fe = [_fe('const data = await fetch("/api/todos");\n')]
        be = [
            _be(
                '@app.get("/api/todos")\nasync def list_todos(): pass\n'
                '@app.get("/api/unused")\nasync def unused(): pass\n'
            )
        ]
        report = check_cross_review(fe, be)
        unused = [f for f in report.findings if f.category == "unused_endpoint"]
        assert len(unused) >= 1

    def test_no_frontend_files(self) -> None:
        report = check_cross_review([], [_be('@app.get("/api/x")\ndef x(): pass\n')])
        assert report.findings == ()
        assert report.frontend_endpoints_called == 0

    def test_no_backend_routes(self) -> None:
        report = check_cross_review([_fe('fetch("/api/x");\n')], [_be("# no routes\n")])
        assert report.findings == ()


class TestNormalizeFieldName:
    def test_snake_case(self) -> None:
        assert _normalize_field_name("created_at") == "created_at"

    def test_camel_case(self) -> None:
        assert _normalize_field_name("createdAt") == "created_at"

    def test_already_lower(self) -> None:
        assert _normalize_field_name("name") == "name"
