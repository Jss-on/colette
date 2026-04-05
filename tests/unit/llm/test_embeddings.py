"""Tests for the shared embeddings utility."""

from __future__ import annotations

import httpx
import pytest
import respx

from colette.llm.embeddings import generate_embeddings
from colette.memory.exceptions import MemoryBackendError


@pytest.mark.unit
class TestGenerateEmbeddings:
    @respx.mock
    async def test_single_text(self) -> None:
        """Single text returns one embedding vector."""
        respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"embedding": [0.1, 0.2, 0.3]}]},
            )
        )

        result = await generate_embeddings(["hello"], api_key="sk-test")
        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

    @respx.mock
    async def test_batch_texts(self) -> None:
        """Multiple texts return matching count of vectors."""
        respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {"embedding": [0.1, 0.2]},
                        {"embedding": [0.3, 0.4]},
                        {"embedding": [0.5, 0.6]},
                    ]
                },
            )
        )

        result = await generate_embeddings(["a", "b", "c"], api_key="sk-test")
        assert len(result) == 3

    @respx.mock
    async def test_custom_base_url(self) -> None:
        """Custom base_url is used for the request."""
        respx.post("https://custom.api/v1/embeddings").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"embedding": [1.0]}]},
            )
        )

        result = await generate_embeddings(
            ["test"],
            api_key="sk-test",
            base_url="https://custom.api/v1",
        )
        assert result == [[1.0]]

    @respx.mock
    async def test_api_key_in_header(self) -> None:
        """API key is sent as Bearer token."""
        route = respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"embedding": [0.0]}]},
            )
        )

        await generate_embeddings(["test"], api_key="my-secret-key")
        assert route.called
        request = route.calls[0].request
        assert request.headers["authorization"] == "Bearer my-secret-key"

    @respx.mock
    async def test_api_failure_raises_memory_backend_error(self) -> None:
        """API errors are wrapped in MemoryBackendError."""
        respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=httpx.Response(500, json={"error": "server error"})
        )

        with pytest.raises(MemoryBackendError):
            await generate_embeddings(["fail"], api_key="sk-test")

    @respx.mock
    async def test_model_passed_in_payload(self) -> None:
        """Custom model name is included in the request payload."""
        route = respx.post("https://api.openai.com/v1/embeddings").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"embedding": [0.0]}]},
            )
        )

        await generate_embeddings(["test"], model="text-embedding-ada-002", api_key="sk-test")
        import json

        payload = json.loads(route.calls[0].request.content)
        assert payload["model"] == "text-embedding-ada-002"
