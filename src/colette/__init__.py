"""Colette — Multi-agent AI system for autonomous end-to-end software development.

Colette is a standalone CLI tool, not a library. Use the CLI (``colette``)
or REST API (``colette serve``) to interact with the system.
"""

__version__ = "0.1.0"

# Colette is NOT a library — prevent wildcard imports.
__all__ = ["__version__"]
