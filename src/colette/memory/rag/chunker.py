"""Recursive text chunker for RAG indexing (FR-MEM-007).

Splits text into chunks of ~512 tokens with 15% overlap.
Code files are split at function/class boundaries.
"""

from __future__ import annotations

import re
import uuid

from colette.llm.token_counter import estimate_tokens
from colette.memory.config import MemorySettings
from colette.memory.models import ChunkRecord

# Regex patterns for code boundary detection
_FUNC_CLASS_RE = re.compile(
    r"^(?:def |class |async def |function |export (?:default )?(?:function |class ))",
    re.MULTILINE,
)


class RecursiveChunker:
    """Splits text into token-bounded chunks with overlap.

    Strategy:
    1. For code: split at function/class boundaries.
    2. For prose: split at paragraphs, then lines, then by token count.
    3. Files under 2000 tokens are kept as a single chunk.
    """

    def __init__(self, settings: MemorySettings | None = None) -> None:
        s = settings or MemorySettings()
        self._chunk_size = s.rag_chunk_size
        self._overlap_pct = s.rag_chunk_overlap_pct

    @property
    def _overlap_tokens(self) -> int:
        return int(self._chunk_size * self._overlap_pct)

    def chunk_text(
        self,
        text: str,
        source_path: str,
        project_id: str = "",
    ) -> list[ChunkRecord]:
        """Split *text* into chunks. Returns a list of ChunkRecords."""
        total_tokens = estimate_tokens(text)

        if total_tokens <= self._chunk_size:
            return [
                ChunkRecord(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    source_path=source_path,
                    content=text,
                    token_count=total_tokens,
                    chunk_index=0,
                    total_chunks=1,
                )
            ]

        is_code = _FUNC_CLASS_RE.search(text) is not None
        if is_code and total_tokens <= 2000:
            return [
                ChunkRecord(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    source_path=source_path,
                    content=text,
                    token_count=total_tokens,
                    chunk_index=0,
                    total_chunks=1,
                )
            ]

        segments = self._split_code(text) if is_code else self._split_prose(text)
        return self._segments_to_chunks(segments, source_path, project_id)

    def _split_code(self, text: str) -> list[str]:
        """Split code at function/class boundaries."""
        boundaries = list(_FUNC_CLASS_RE.finditer(text))
        if not boundaries:
            return self._split_prose(text)

        segments: list[str] = []
        for i, match in enumerate(boundaries):
            start = match.start()
            end = boundaries[i + 1].start() if i + 1 < len(boundaries) else len(text)
            segment = text[start:end].rstrip()
            if segment:
                segments.append(segment)

        # Prepend any header before the first boundary
        header = text[: boundaries[0].start()].strip()
        if header:
            segments.insert(0, header)

        return segments

    def _split_prose(self, text: str) -> list[str]:
        """Split prose at paragraphs, then lines if too large."""
        paragraphs = re.split(r"\n\n+", text)
        segments: list[str] = []
        for para in paragraphs:
            stripped = para.strip()
            if not stripped:
                continue
            if estimate_tokens(stripped) <= self._chunk_size:
                segments.append(stripped)
            else:
                # Split long paragraphs by lines
                for line in stripped.split("\n"):
                    line = line.strip()
                    if line:
                        segments.append(line)
        return segments

    def _segments_to_chunks(
        self,
        segments: list[str],
        source_path: str,
        project_id: str,
    ) -> list[ChunkRecord]:
        """Merge segments into token-bounded chunks with overlap."""
        chunks: list[ChunkRecord] = []
        current_parts: list[str] = []
        current_tokens = 0

        for segment in segments:
            seg_tokens = estimate_tokens(segment)

            if current_tokens + seg_tokens > self._chunk_size and current_parts:
                chunk_content = "\n\n".join(current_parts)
                chunks.append(
                    ChunkRecord(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        source_path=source_path,
                        content=chunk_content,
                        token_count=estimate_tokens(chunk_content),
                        chunk_index=len(chunks),
                        total_chunks=0,  # patched below
                    )
                )
                # Overlap: keep the last part(s) if they fit
                overlap_parts: list[str] = []
                overlap_tokens = 0
                for part in reversed(current_parts):
                    pt = estimate_tokens(part)
                    if overlap_tokens + pt <= self._overlap_tokens:
                        overlap_parts.insert(0, part)
                        overlap_tokens += pt
                    else:
                        break
                current_parts = overlap_parts
                current_tokens = overlap_tokens

            current_parts.append(segment)
            current_tokens += seg_tokens

        # Flush remaining
        if current_parts:
            chunk_content = "\n\n".join(current_parts)
            chunks.append(
                ChunkRecord(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    source_path=source_path,
                    content=chunk_content,
                    token_count=estimate_tokens(chunk_content),
                    chunk_index=len(chunks),
                    total_chunks=0,
                )
            )

        # Patch total_chunks
        total = len(chunks)
        return [
            ChunkRecord(
                id=c.id,
                project_id=c.project_id,
                source_path=c.source_path,
                content=c.content,
                token_count=c.token_count,
                chunk_index=c.chunk_index,
                total_chunks=total,
            )
            for c in chunks
        ]
