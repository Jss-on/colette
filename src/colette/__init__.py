"""Colette — Multi-agent AI system for autonomous end-to-end software development.

Colette is a standalone CLI tool, not a library. Use the CLI (``colette``)
or REST API (``colette serve``) to interact with the system.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("colette")
except PackageNotFoundError:
    try:
        from colette._version import __version__
    except ImportError:
        __version__ = "0.0.0-dev"

# Colette is NOT a library — prevent wildcard imports.
__all__ = ["__version__"]
