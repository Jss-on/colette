"""Async embedding generation via OpenAI-compatible API."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)

_DEFAULT_EMBEDDINGS_BASE_URL = "https://api.openai.com/v1"


async def generate_embeddings(
    texts: list[str],
    *,
    model: str = "text-embedding-3-large",
    api_key: str = "",
    base_url: str = _DEFAULT_EMBEDDINGS_BASE_URL,
) -> list[list[float]]:
    """Generate embeddings via an OpenAI-compatible /embeddings endpoint.

    Args:
        texts: Texts to embed.
        model: Embedding model identifier.
        api_key: Bearer token for the embeddings API.
        base_url: API base URL (defaults to OpenAI).

    Returns:
        List of embedding vectors.

    Raises:
        MemoryBackendError: On API failure.
    """
    from colette.memory.exceptions import MemoryBackendError

    url = f"{base_url.rstrip('/')}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": model, "input": texts}

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()["data"]
            return [item["embedding"] for item in data]
    except Exception as exc:
        raise MemoryBackendError("embedding", str(exc)) from exc
