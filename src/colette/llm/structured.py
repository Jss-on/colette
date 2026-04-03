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


def _parse_structured_response[T: BaseModel](
    raw_text: str,
    output_type: type[T],
) -> T:
    """Parse an LLM text response into *output_type* via JSON extraction.

    Tries ``model_validate_json`` first, then falls back to ``model_validate``
    with ``json.loads`` for looser parsing.

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

    async with _llm_semaphore:
        logger.debug(
            "llm_semaphore_acquired",
            output_type=output_type.__name__,
            tier=str(model_tier),
            streaming=stream_enabled,
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

    return _parse_structured_response(full_text, output_type)
