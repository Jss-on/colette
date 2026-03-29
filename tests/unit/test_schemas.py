"""Tests for base handoff schema."""

from colette.schemas.base import HandoffSchema


def test_handoff_schema_defaults() -> None:
    h = HandoffSchema(
        schema_version="1.0.0",
        project_id="proj-001",
        source_stage="requirements",
        target_stage="design",
    )
    assert h.schema_version == "1.0.0"
    assert h.quality_gate_passed is False
    assert h.metadata == {}
    assert h.created_at is not None
