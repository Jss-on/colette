"""Tests for the structured LLM output helper."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from colette.llm.structured import (
    _repair_truncated_json,
    extract_json_block,
    invoke_structured,
)

# ── extract_json_block ──────────────────────────────────────────────────


class TestExtractJsonBlock:
    def test_json_fence(self) -> None:
        text = 'Here is the result:\n```json\n{"key": "value"}\n```\nDone.'
        assert extract_json_block(text) == '{"key": "value"}'

    def test_plain_fence(self) -> None:
        text = '```\n{"key": "value"}\n```'
        assert extract_json_block(text) == '{"key": "value"}'

    def test_raw_json(self) -> None:
        text = '{"key": "value"}'
        assert extract_json_block(text) == '{"key": "value"}'

    def test_json_with_surrounding_text(self) -> None:
        text = 'Some prefix {"key": "value"} some suffix'
        result = extract_json_block(text)
        assert '"key"' in result

    def test_no_json(self) -> None:
        text = "No JSON here"
        assert extract_json_block(text) == text

    def test_array_in_json_fence(self) -> None:
        text = '```json\n[{"a": 1}]\n```'
        assert extract_json_block(text) == '[{"a": 1}]'


# ── invoke_structured ───────────────────────────────────────────────────


class SimpleModel(BaseModel):
    name: str
    count: int = Field(ge=0)


class TestInvokeStructured:
    @pytest.mark.asyncio
    async def test_parses_json_response(self) -> None:
        mock_response = MagicMock()
        mock_response.content = '{"name": "test", "count": 5}'

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "colette.llm.structured.create_chat_model_for_tier",
            return_value=mock_model,
        ):
            result = await invoke_structured(
                system_prompt="Test",
                user_content="Test input",
                output_type=SimpleModel,
            )

        assert result.name == "test"
        assert result.count == 5

    @pytest.mark.asyncio
    async def test_parses_json_in_fence(self) -> None:
        mock_response = MagicMock()
        mock_response.content = '```json\n{"name": "fenced", "count": 3}\n```'

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "colette.llm.structured.create_chat_model_for_tier",
            return_value=mock_model,
        ):
            result = await invoke_structured(
                system_prompt="Test",
                user_content="Test input",
                output_type=SimpleModel,
            )

        assert result.name == "fenced"
        assert result.count == 3

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self) -> None:
        mock_response = MagicMock()
        mock_response.content = "not json at all"

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with (
            patch(
                "colette.llm.structured.create_chat_model_for_tier",
                return_value=mock_model,
            ),
            pytest.raises(ValueError, match="Failed to parse"),
        ):
            await invoke_structured(
                system_prompt="Test",
                user_content="Test input",
                output_type=SimpleModel,
            )

    @pytest.mark.asyncio
    async def test_retries_on_parse_failure_then_succeeds(self) -> None:
        """Second LLM call returns valid JSON after first returns truncated."""
        bad_response = MagicMock()
        bad_response.content = '{"name": "trunc'  # truncated, unrepairable for SimpleModel

        good_response = MagicMock()
        good_response.content = '{"name": "ok", "count": 1}'

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(side_effect=[bad_response, good_response])

        with patch(
            "colette.llm.structured.create_chat_model_for_tier",
            return_value=mock_model,
        ):
            result = await invoke_structured(
                system_prompt="Test",
                user_content="Test input",
                output_type=SimpleModel,
            )

        assert result.name == "ok"
        assert result.count == 1

    @pytest.mark.asyncio
    async def test_repairs_truncated_json(self) -> None:
        """Truncated JSON with missing closing braces gets repaired."""
        mock_response = MagicMock()
        # Simulate truncated output: missing closing brace
        mock_response.content = '{"name": "repaired", "count": 7'

        mock_model = AsyncMock()
        mock_model.ainvoke = AsyncMock(return_value=mock_response)

        with patch(
            "colette.llm.structured.create_chat_model_for_tier",
            return_value=mock_model,
        ):
            result = await invoke_structured(
                system_prompt="Test",
                user_content="Test input",
                output_type=SimpleModel,
            )

        assert result.name == "repaired"
        assert result.count == 7


# ── _repair_truncated_json ─────────────────────────────────────────────


class TestRepairTruncatedJson:
    def test_closes_missing_brace(self) -> None:
        result = _repair_truncated_json('{"a": 1')
        assert result == '{"a": 1}'

    def test_closes_missing_bracket_and_brace(self) -> None:
        result = _repair_truncated_json('{"items": [1, 2')
        assert result == '{"items": [1, 2]}'

    def test_removes_trailing_comma(self) -> None:
        result = _repair_truncated_json('{"items": [1, 2,')
        assert result == '{"items": [1, 2]}'

    def test_closes_truncated_string(self) -> None:
        result = _repair_truncated_json('{"name": "hello')
        assert result == '{"name": "hello"}'

    def test_valid_json_unchanged(self) -> None:
        valid = '{"a": 1}'
        assert _repair_truncated_json(valid) == valid
