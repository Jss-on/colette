"""Smoke test — verify package is importable and version is set."""

import re

from colette import __version__


def test_version_is_set() -> None:
    """Version should be a valid PEP 440 string, not the dev fallback."""
    assert __version__ != "0.0.0-dev"
    # Matches semver (0.1.0) or dev versions (0.1.1.dev29+g1a2b3c4.d20260403)
    assert re.match(r"^\d+\.\d+\.\d+", __version__)
