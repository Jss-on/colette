"""Tests for artifact packaging."""

from __future__ import annotations

import zipfile
from io import BytesIO

from colette.artifacts import collect_generated_files, create_artifact_zip


def test_collect_generated_files_from_handoffs() -> None:
    state = {
        "handoffs": {
            "implementation": {
                "generated_files": [
                    {"path": "src/main.py", "content": "print('hello')"},
                    {"path": "src/app.ts", "content": "console.log('hi')"},
                ]
            },
            "testing": {
                "generated_files": [
                    {"path": "tests/test_main.py", "content": "assert True"},
                ]
            },
        }
    }
    files = collect_generated_files(state)
    assert len(files) == 3
    paths = [f["path"] for f in files]
    assert "src/main.py" in paths
    assert "tests/test_main.py" in paths


def test_collect_generated_files_empty_state() -> None:
    files = collect_generated_files({})
    assert files == []


def test_collect_generated_files_skips_invalid() -> None:
    state = {
        "handoffs": {
            "implementation": {
                "generated_files": [
                    {"path": "valid.py", "content": "ok"},
                    "not-a-dict",
                    {"no_path_key": True},
                ]
            }
        }
    }
    files = collect_generated_files(state)
    assert len(files) == 1


def test_create_artifact_zip() -> None:
    files = [
        {"path": "src/main.py", "content": "print('hello')"},
        {"path": "README.md", "content": "# Hello"},
    ]
    data = create_artifact_zip(files)
    assert isinstance(data, bytes)

    buf = BytesIO(data)
    with zipfile.ZipFile(buf) as zf:
        names = zf.namelist()
        assert "src/main.py" in names
        assert "README.md" in names
        assert zf.read("src/main.py") == b"print('hello')"


def test_create_artifact_zip_empty() -> None:
    data = create_artifact_zip([])
    buf = BytesIO(data)
    with zipfile.ZipFile(buf) as zf:
        assert len(zf.namelist()) == 0
