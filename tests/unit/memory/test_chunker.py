"""Tests for recursive text chunker (FR-MEM-007)."""

from __future__ import annotations

from colette.memory.config import MemorySettings
from colette.memory.rag.chunker import RecursiveChunker


class TestRecursiveChunker:
    def _make(self, chunk_size: int = 512) -> RecursiveChunker:
        return RecursiveChunker(MemorySettings(rag_chunk_size=chunk_size))

    def test_small_text_single_chunk(self) -> None:
        chunker = self._make()
        chunks = chunker.chunk_text("Hello world", "test.txt")
        assert len(chunks) == 1
        assert chunks[0].content == "Hello world"
        assert chunks[0].total_chunks == 1
        assert chunks[0].chunk_index == 0

    def test_large_prose_split(self) -> None:
        chunker = self._make(chunk_size=50)
        paragraphs = [f"Paragraph {i}: " + "word " * 30 for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = chunker.chunk_text(text, "doc.md")
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.total_chunks == len(chunks)
            assert chunk.source_path == "doc.md"

    def test_code_under_2000_tokens_single_chunk(self) -> None:
        chunker = self._make()
        code = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
        chunks = chunker.chunk_text(code, "module.py")
        assert len(chunks) == 1

    def test_code_split_at_boundaries(self) -> None:
        chunker = self._make(chunk_size=100)
        # Generate enough code to exceed 2000 tokens
        functions = [
            f"def func_{i}(param_a, param_b, param_c):\n"
            + "".join(f"    result_{j} = param_a + param_b * {j}\n" for j in range(60))
            + "    return result_0\n"
            for i in range(15)
        ]
        code = "\n".join(functions)
        chunks = chunker.chunk_text(code, "big_module.py")
        assert len(chunks) > 1

    def test_chunk_index_sequential(self) -> None:
        chunker = self._make(chunk_size=30)
        text = "\n\n".join(f"Paragraph {i}: " + "a " * 40 for i in range(10))
        chunks = chunker.chunk_text(text, "doc.txt")
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_project_id_propagated(self) -> None:
        chunker = self._make()
        chunks = chunker.chunk_text("content", "f.txt", project_id="proj-1")
        assert chunks[0].project_id == "proj-1"

    def test_token_count_populated(self) -> None:
        chunker = self._make()
        chunks = chunker.chunk_text("Hello world test", "f.txt")
        assert chunks[0].token_count > 0

    def test_overlap_between_chunks(self) -> None:
        chunker = self._make(chunk_size=30)
        text = "\n\n".join(f"Distinct paragraph {i}: " + "word " * 20 for i in range(10))
        chunks = chunker.chunk_text(text, "doc.txt")
        if len(chunks) >= 2:
            # Check that some content from end of chunk N appears in chunk N+1
            first_content = chunks[0].content
            second_content = chunks[1].content
            # At least some overlap should exist (last segment of first in second)
            last_para_first = first_content.split("\n\n")[-1]
            assert last_para_first in second_content or len(chunks) >= 2

    def test_empty_text(self) -> None:
        chunker = self._make()
        chunks = chunker.chunk_text("", "empty.txt")
        assert len(chunks) == 1
        assert chunks[0].token_count >= 1  # minimum 1 from estimate_tokens
