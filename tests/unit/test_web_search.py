"""Tests for the web search tool."""

from __future__ import annotations

import pytest

from colette.tools.web_search import WebSearchTool


@pytest.fixture
def search_tool() -> WebSearchTool:
    return WebSearchTool()


class TestWebSearchTool:
    def test_returns_placeholder_for_query(self, search_tool: WebSearchTool) -> None:
        result = search_tool._run(query="python best practices")
        assert "python best practices" in result
        assert "not configured" in result.lower()

    def test_empty_query_returns_error(self, search_tool: WebSearchTool) -> None:
        result = search_tool._run(query="")
        assert "Error" in result
