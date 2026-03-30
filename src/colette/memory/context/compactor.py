"""Verbatim context compaction (FR-MEM-005).

Implements segment-level verbatim extraction — no summarization.
Splits content into segments, scores by information density, and
greedily selects highest-density segments to fit the target.
"""

from __future__ import annotations

import re

import structlog

from colette.llm.token_counter import estimate_tokens
from colette.memory.models import CompactionResult

logger = structlog.get_logger(__name__)

# Regex for splitting content into segments
_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_PARAGRAPH_RE = re.compile(r"\n\n+")


def _score_segment(segment: str) -> float:
    """Score a segment by information density.

    Higher scores for code, data, and structured content.
    Lower scores for prose, filler, and whitespace.
    """
    tokens = estimate_tokens(segment)
    if tokens == 0:
        return 0.0

    score = 1.0
    # Code blocks and structured data are high-value
    if "```" in segment or segment.strip().startswith(("{", "[", "def ", "class ")):
        score += 2.0
    # Lines with key-value patterns (config, env vars, JSON)
    kv_lines = len(re.findall(r"^\s*\w+\s*[:=]", segment, re.MULTILINE))
    score += min(kv_lines * 0.3, 2.0)
    # Bullet/numbered lists
    list_lines = len(re.findall(r"^\s*[-*\d]+[.)]\s", segment, re.MULTILINE))
    score += min(list_lines * 0.2, 1.0)
    # Penalize very short segments
    if tokens < 10:
        score *= 0.5
    return score


def _split_into_segments(content: str) -> list[str]:
    """Split content into meaningful segments."""
    segments: list[str] = []

    # Extract code blocks first
    parts = _CODE_BLOCK_RE.split(content)
    code_blocks = _CODE_BLOCK_RE.findall(content)

    for i, part in enumerate(parts):
        # Add paragraphs from non-code sections
        paragraphs = _PARAGRAPH_RE.split(part.strip())
        for para in paragraphs:
            stripped = para.strip()
            if stripped:
                segments.append(stripped)
        # Re-insert code block after corresponding part
        if i < len(code_blocks):
            segments.append(code_blocks[i])

    return segments if segments else [content]


class VerbatimCompactor:
    """Compacts content by selecting high-density segments verbatim.

    No summarization — preserves exact text of selected segments.
    Triggered at 70% context utilization per FR-MEM-005.
    """

    def compact(self, content: str, target_tokens: int) -> CompactionResult:
        """Select highest-density segments to fit within *target_tokens*."""
        original_tokens = estimate_tokens(content)

        if original_tokens <= target_tokens:
            return CompactionResult(
                original_tokens=original_tokens,
                compacted_tokens=original_tokens,
                reduction_ratio=0.0,
                compacted_content=content,
            )

        segments = _split_into_segments(content)

        # Score and sort by density (highest first)
        scored = [(seg, _score_segment(seg)) for seg in segments]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Greedily select segments
        selected: list[tuple[str, int]] = []  # (segment, original_index)
        used_tokens = 0
        for seg, _score in scored:
            seg_tokens = estimate_tokens(seg)
            if used_tokens + seg_tokens <= target_tokens:
                # Track original order for reassembly
                orig_idx = segments.index(seg)
                selected.append((seg, orig_idx))
                used_tokens += seg_tokens

        # Reassemble in original order
        selected.sort(key=lambda x: x[1])
        compacted = "\n\n".join(seg for seg, _ in selected)
        compacted_tokens = estimate_tokens(compacted)

        reduction = 1.0 - (compacted_tokens / original_tokens) if original_tokens > 0 else 0.0

        logger.info(
            "context_compacted",
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            reduction_ratio=round(reduction, 3),
            segments_total=len(segments),
            segments_kept=len(selected),
        )

        return CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            reduction_ratio=round(reduction, 3),
            compacted_content=compacted,
        )

    def compact_messages(
        self,
        messages: list[dict[str, str]],
        target_tokens: int,
        *,
        keep_recent: int = 10,
    ) -> tuple[list[dict[str, str]], CompactionResult | None]:
        """Compact a message list, keeping system and recent messages intact.

        Returns the (compacted messages, CompactionResult or None if no compaction needed).
        """
        if len(messages) <= keep_recent:
            return messages, None

        # Always keep system messages and the last `keep_recent` messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        recent = non_system[-keep_recent:]
        older = non_system[:-keep_recent]

        if not older:
            return messages, None

        # Compact the older messages into a single summary segment
        older_text = "\n\n".join(
            f"[{m.get('role', 'unknown')}]: {m.get('content', '')}" for m in older
        )
        available = max(
            target_tokens
            - sum(estimate_tokens(m.get("content", "")) for m in system_msgs + recent),
            100,
        )

        result = self.compact(older_text, available)

        compacted_msg: dict[str, str] = {
            "role": "system",
            "content": f"[Compacted conversation history]\n{result.compacted_content}",
        }

        return [*system_msgs, compacted_msg, *recent], result
