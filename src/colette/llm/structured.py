"""Structured LLM output extraction (FR-REQ-003, FR-DES-002).

Provides ``invoke_structured()`` which calls the LLM and parses
the response into a typed Pydantic model via JSON extraction.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from colette.llm.gateway import create_chat_model_for_tier
from colette.schemas.agent_config import ModelTier

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)

def extract_json_block(text: str) -> str:
    """Extract a JSON object or array from LLM text, handling markdown fences.

    Tries in order: ```json fence, ``` fence, raw braces.
    """
    # ```json { ... } ```
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
    # Raw JSON (first outermost braces)
    match = re.search(r"(\{[\s\S]*\})", text)
    if match:
        return match.group(1)
    return text


async def invoke_structured[T: BaseModel](
    system_prompt: str,
    user_content: str,
    output_type: type[T],
    *,
    settings: Settings | None = None,
    model_tier: ModelTier = ModelTier.EXECUTION,
) -> T:
    """Invoke the LLM and parse the response as a typed Pydantic model.

    The system prompt is augmented with the JSON schema of *output_type*
    and explicit instructions to output only valid JSON.

    Parameters
    ----------
    system_prompt:
        Domain-specific instructions for the LLM.
    user_content:
        The user-facing content (project description, PRD, etc.).
    output_type:
        Pydantic model class to parse the response into.
    settings:
        Application settings.  Loaded from env if ``None``.
    model_tier:
        Which model tier to use (planning, execution, validation).

    Returns
    -------
    T
        An instance of *output_type* parsed from the LLM's JSON response.

    Raises
    ------
    ValueError
        If the LLM response cannot be parsed into *output_type*.
    """
    if settings is None:
        from colette.config import Settings as _Settings

        settings = _Settings()

    schema = json.dumps(output_type.model_json_schema(), indent=2)
    full_prompt = (
        f"{system_prompt}\n\n"
        "You MUST respond with valid JSON matching this schema. "
        "Do NOT include any text outside the JSON object.\n\n"
        f"JSON Schema:\n```json\n{schema}\n```"
    )

    model = create_chat_model_for_tier(model_tier, settings=settings)
    response = await model.ainvoke(
        [
            SystemMessage(content=full_prompt),
            HumanMessage(content=user_content),
        ]
    )

    raw_text = str(response.content)
    json_str = extract_json_block(raw_text)

    try:
        return output_type.model_validate_json(json_str)
    except Exception:
        # Fall back to dict-based validation for looser parsing
        try:
            data: object = json.loads(json_str)
            return output_type.model_validate(data)
        except Exception as exc:
            logger.error(
                "structured_output_parse_error",
                output_type=output_type.__name__,
                raw_length=len(raw_text),
                error=str(exc),
            )
            raise ValueError(
                f"Failed to parse LLM output as {output_type.__name__}: {exc}"
            ) from exc
