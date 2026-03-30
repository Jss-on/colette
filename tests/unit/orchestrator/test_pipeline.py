"""Tests for pipeline graph construction."""

from __future__ import annotations

from colette.config import Settings
from colette.gates import create_default_registry
from colette.orchestrator.pipeline import build_pipeline


class TestBuildPipeline:
    def test_compiles_successfully(self) -> None:
        registry = create_default_registry()
        settings = Settings()
        graph = build_pipeline(registry, settings)
        assert graph is not None

    def test_has_stage_nodes(self) -> None:
        registry = create_default_registry()
        settings = Settings()
        graph = build_pipeline(registry, settings)
        nodes = graph.get_graph().nodes
        stages = (
            "requirements",
            "design",
            "implementation",
            "testing",
            "deployment",
            "monitoring",
        )
        for stage in stages:
            assert f"stage_{stage}" in nodes

    def test_has_gate_nodes(self) -> None:
        registry = create_default_registry()
        settings = Settings()
        graph = build_pipeline(registry, settings)
        nodes = graph.get_graph().nodes
        for gate in ("requirements", "design", "implementation", "testing", "staging"):
            assert f"gate_{gate}" in nodes
