"""Web search tool for domain research (FR-REQ-004).

In production, configure ``TAVILY_API_KEY`` or ``SERP_API_KEY`` for
live results.  The default implementation returns a placeholder so
the pipeline can proceed without external API dependencies.
"""

from __future__ import annotations

from typing import Any

from colette.tools.base import MCPBaseTool


class WebSearchTool(MCPBaseTool):
    """Search the web for domain knowledge and technical references."""

    name: str = "web_search"
    description: str = (
        "Search the web for information. Input should be a search query string. "
        "Returns relevant snippets and URLs."
    )

    def _execute(self, *, query: str = "", **kwargs: Any) -> str:
        """Execute web search.  Override in production with a real API."""
        if not query:
            return "Error: No search query provided."
        return (
            f"[Web search results for: {query}]\n"
            "Note: Web search is not configured. "
            "Using LLM knowledge for domain research. "
            "Configure a search API (TAVILY_API_KEY or SERP_API_KEY) "
            "for live web search results."
        )
