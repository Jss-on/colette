"""Auto-apply 'integration' marker to all tests in this directory."""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Add 'integration' marker to all tests under tests/integration/."""
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
