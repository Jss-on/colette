"""Structured LLM output extraction (FR-REQ-003, FR-DES-002).

Provides ``invoke_structured()`` which calls the LLM and parses
the response into a typed Pydantic model via JSON extraction.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import TYPE_CHECKING

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from colette.llm.cache import build_cached_system_message
from colette.llm.gateway import create_chat_model_for_tier
from colette.schemas.agent_config import ModelTier
from colette.tools.base import sanitize_output

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)

# Global semaphore to cap concurrent LLM calls and avoid rate-limit storms.
# Initialized lazily from settings on first use.
_llm_semaphore: asyncio.Semaphore | None = None
_llm_semaphore_size: int = 0


def extract_json_block(text: str) -> str:
    """Extract a JSON object or array from LLM text, handling markdown fences.

    Tries in order: ```json fence, ``` fence, raw braces, raw brackets.
    """
    # ```json { ... } ``` or ```json [ ... ] ```
    match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"```json\s*(\[.*\])\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # ``` { ... } ```
    match = re.search(r"```\s*(\{.*\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # Raw JSON object (first outermost braces)
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        return match.group(1)
    # Raw JSON array
    match = re.search(r"(\[[\s\S]*\])", text)
    if match:
        return match.group(1)
    return text


def _build_structured_prompt(system_prompt: str, output_type: type[BaseModel]) -> str:
    """Augment a system prompt with the JSON schema of *output_type*."""
    schema = json.dumps(output_type.model_json_schema(), indent=2)
    return (
        f"{system_prompt}\n\n"
        "You MUST respond with valid JSON matching this schema. "
        "Do NOT include any text outside the JSON object.\n\n"
        f"JSON Schema:\n```json\n{schema}\n```"
    )


def _repair_truncated_json(json_str: str) -> str:
    """Attempt to repair truncated JSON by closing open brackets/braces.

    Handles common LLM truncation patterns: output cut off mid-array
    or mid-object, trailing commas before a missing closing bracket.
    """
    # Strip trailing whitespace
    repaired = json_str.rstrip()

    # Remove trailing comma (invalid before a closing bracket)
    repaired = re.sub(r",\s*$", "", repaired)

    # Count open vs close brackets/braces
    open_braces = repaired.count("{") - repaired.count("}")
    open_brackets = repaired.count("[") - repaired.count("]")

    # If we're inside a string literal that was truncated, close it
    # by checking if quote count is odd.
    in_string = False
    escape = False
    for ch in repaired:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string

    if in_string:
        repaired += '"'

    # Remove any trailing comma after string repair
    repaired = re.sub(r",\s*$", "", repaired)

    # Close open brackets/braces in reverse order of nesting
    repaired += "]" * max(0, open_brackets)
    repaired += "}" * max(0, open_braces)

    return repaired


def _parse_structured_response[T: BaseModel](
    raw_text: str,
    output_type: type[T],
) -> T:
    """Parse an LLM text response into *output_type* via JSON extraction.

    Tries ``model_validate_json`` first, then falls back to ``model_validate``
    with ``json.loads`` for looser parsing.  As a last resort, attempts to
    repair truncated JSON (unclosed brackets/braces).

    Raises
    ------
    ValueError
        If the response cannot be parsed.
    """
    json_str = extract_json_block(raw_text)

    try:
        return output_type.model_validate_json(json_str)
    except Exception as first_exc:
        logger.debug("structured_output_first_parse_failed", error=str(first_exc))
        try:
            data: object = json.loads(json_str)
            return output_type.model_validate(data)
        except Exception as second_exc:
            logger.debug("structured_output_second_parse_failed", error=str(second_exc))

        # Attempt to repair truncated JSON before giving up.
        try:
            repaired = _repair_truncated_json(json_str)
            logger.warning(
                "structured_output_repair_attempt",
                output_type=output_type.__name__,
                original_len=len(json_str),
                repaired_len=len(repaired),
            )
            data = json.loads(repaired)
            result = output_type.model_validate(data)
            logger.info(
                "structured_output_repair_success",
                output_type=output_type.__name__,
            )
            return result
        except Exception as exc:
            logger.error(
                "structured_output_parse_error",
                output_type=output_type.__name__,
                raw_length=len(raw_text),
            )
            raise ValueError(
                f"Failed to parse LLM output as {output_type.__name__}: {exc}"
            ) from exc


async def invoke_structured[T: BaseModel](
    system_prompt: str,
    user_content: str,
    output_type: type[T],
    *,
    settings: Settings | None = None,
    model_tier: ModelTier = ModelTier.EXECUTION,
) -> T:
    """Invoke the LLM and parse the response as a typed Pydantic model.

    The system prompt is augmented with the JSON schema of *output_type*.
    User content is sanitized to strip prompt-injection markers before
    being sent to the LLM (FR-TL-004).

    When pipeline context variables are set, a callback is attached to
    emit agent-level events (AGENT_THINKING, AGENT_MESSAGE) to the SSE
    stream.

    Raises
    ------
    ValueError
        If the LLM response cannot be parsed into *output_type*.
    """
    if settings is None:
        from colette.config import Settings as _Settings

        settings = _Settings()

    # Lazily initialize the concurrency semaphore.
    global _llm_semaphore, _llm_semaphore_size
    if _llm_semaphore is None or _llm_semaphore_size != settings.llm_max_concurrency:
        _llm_semaphore_size = settings.llm_max_concurrency
        _llm_semaphore = asyncio.Semaphore(_llm_semaphore_size)

    # Sanitize user content to strip prompt-injection markers (H1)
    safe_content = sanitize_output(user_content)

    full_prompt = _build_structured_prompt(system_prompt, output_type)
    model = create_chat_model_for_tier(model_tier, settings=settings)

    # Attach callback for agent-level event bus emission (Phase 7).
    from colette.observability.callbacks import ColletteCallbackHandler

    callback = ColletteCallbackHandler(
        agent_id=f"structured-{output_type.__name__}",
        agent_role=output_type.__name__,
        model=str(model_tier),
    )

    # Build system message with Anthropic prompt caching when enabled.
    if settings.prompt_caching_enabled:
        sys_msg = build_cached_system_message(full_prompt)
    else:
        sys_msg = SystemMessage(content=full_prompt)

    # Enable streaming when the event bus is active so on_llm_new_token
    # fires and AGENT_STREAM_CHUNK events reach the TUI in real-time.
    from colette.orchestrator.event_bus import event_bus_var

    stream_enabled = event_bus_var.get() is not None

    from langchain_core.runnables import RunnableConfig

    messages = [sys_msg, HumanMessage(content=safe_content)]
    config = RunnableConfig(callbacks=[callback])

    max_parse_retries = settings.llm_max_retries
    last_exc: Exception | None = None

    for attempt in range(1 + max_parse_retries):
        async with _llm_semaphore:
            logger.debug(
                "llm_semaphore_acquired",
                output_type=output_type.__name__,
                tier=str(model_tier),
                streaming=stream_enabled,
                attempt=attempt + 1,
            )
            if stream_enabled:
                # Stream tokens for real-time display; accumulate full text.
                chunks: list[str] = []
                async for chunk in model.astream(messages, config=config):
                    chunks.append(str(chunk.content))
                full_text = "".join(chunks)
            else:
                response = await model.ainvoke(messages, config=config)
                full_text = str(response.content)

        try:
            return _parse_structured_response(full_text, output_type)
        except ValueError as exc:
            last_exc = exc
            if attempt < max_parse_retries:
                logger.warning(
                    "structured_output_retry",
                    output_type=output_type.__name__,
                    attempt=attempt + 1,
                    max_retries=max_parse_retries,
                    error=str(exc)[:200],
                )
                # Continue to next attempt — the LLM may produce valid JSON on retry.
            else:
                raise

    # Should be unreachable, but satisfy type checker.
    assert last_exc is not None
    raise last_exc
