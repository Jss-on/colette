"""Tests that Colette cannot be used as a library."""

from __future__ import annotations


def test_all_only_exports_version() -> None:
    import colette

    assert colette.__all__ == ["__version__"]


def test_version_is_string() -> None:
    from colette import __version__

    assert isinstance(__version__, str)
    assert "." in __version__
