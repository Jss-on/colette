"""Smoke test — verify package is importable and version is set."""

from colette import __version__


def test_version_is_set() -> None:
    assert __version__ == "0.1.0"
