"""Tests for colette.eval.security_patterns."""

from __future__ import annotations

from colette.eval.security_patterns import scan_files


def _file(content: str, path: str = "app.py") -> dict[str, str]:
    return {"path": path, "content": content}


class TestScanFiles:
    def test_sql_fstring(self) -> None:
        code = 'db.execute(f"SELECT * FROM users WHERE id={user_id}")\n'
        report = scan_files([_file(code)])
        assert report.has_blocking is True
        sql_matches = [m for m in report.matches if m.pattern_id == "SEC-SQL-001"]
        assert len(sql_matches) >= 1

    def test_sql_parameterized_no_match(self) -> None:
        code = 'db.execute("SELECT * FROM users WHERE id=?", (user_id,))\n'
        report = scan_files([_file(code)])
        sql_matches = [m for m in report.matches if m.category == "sql_injection"]
        assert len(sql_matches) == 0

    def test_hardcoded_secret(self) -> None:
        code = 'api_key = "sk-1234567890abcdef"\n'
        report = scan_files([_file(code)])
        cred_matches = [m for m in report.matches if m.pattern_id == "SEC-CRED-001"]
        assert len(cred_matches) >= 1

    def test_env_var_secret_suppressed(self) -> None:
        code = 'api_key = os.environ["API_KEY"]\n'
        report = scan_files([_file(code)])
        cred_matches = [m for m in report.matches if m.pattern_id == "SEC-CRED-001"]
        assert len(cred_matches) == 0

    def test_test_secret_suppressed(self) -> None:
        code = 'password = "test_password_for_testing"\n'
        report = scan_files([_file(code)])
        cred_matches = [m for m in report.matches if m.pattern_id == "SEC-CRED-001"]
        assert len(cred_matches) == 0

    def test_xss_dangerously_set(self) -> None:
        code = "<div dangerouslySetInnerHTML={{__html: userInput}} />\n"
        report = scan_files([_file(code, "component.tsx")])
        xss_matches = [m for m in report.matches if m.pattern_id == "SEC-XSS-001"]
        assert len(xss_matches) >= 1

    def test_xss_with_dompurify_suppressed(self) -> None:
        code = "<div dangerouslySetInnerHTML={{__html: DOMPurify.sanitize(html)}} />\n"
        report = scan_files([_file(code, "component.tsx")])
        xss_matches = [m for m in report.matches if m.pattern_id == "SEC-XSS-001"]
        assert len(xss_matches) == 0

    def test_consolidation(self) -> None:
        files = [_file('db.execute(f"SELECT {x}")\n', f"file{i}.py") for i in range(5)]
        report = scan_files(files)
        sql_matches = [m for m in report.matches if m.pattern_id == "SEC-SQL-001"]
        assert len(sql_matches) == 5
        assert report.files_scanned == 5

    def test_empty_files(self) -> None:
        report = scan_files([])
        assert report.matches == ()
        assert report.has_blocking is False
        assert report.files_scanned == 0

    def test_eval_detected(self) -> None:
        code = "result = eval(user_input)\n"
        report = scan_files([_file(code)])
        eval_matches = [m for m in report.matches if m.pattern_id == "SEC-EVAL-001"]
        assert len(eval_matches) >= 1

    def test_literal_eval_suppressed(self) -> None:
        code = "result = ast.literal_eval(data)\n"
        report = scan_files([_file(code)])
        eval_matches = [m for m in report.matches if m.pattern_id == "SEC-EVAL-001"]
        assert len(eval_matches) == 0
