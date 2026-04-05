"""Tests for module design schemas (Phase 2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from colette.schemas.module_design import (
    DataFlowEdge,
    InterfaceContract,
    ModuleDesign,
    ModuleSpec,
    TestStrategy,
)


class TestModuleSpec:
    def test_minimal(self) -> None:
        spec = ModuleSpec(file_path="src/main.py", responsibility="Entry point")
        assert spec.file_path == "src/main.py"
        assert spec.public_api == []

    def test_frozen(self) -> None:
        spec = ModuleSpec(file_path="a.py", responsibility="x")
        with pytest.raises(ValidationError):
            spec.file_path = "b.py"  # type: ignore[misc]


class TestInterfaceContract:
    def test_full(self) -> None:
        contract = InterfaceContract(
            name="create_user",
            input_types={"name": "str", "email": "str"},
            output_type="User",
            preconditions=["email is valid"],
            postconditions=["user exists in DB"],
        )
        assert contract.name == "create_user"
        assert len(contract.input_types) == 2
        assert contract.output_type == "User"

    def test_defaults(self) -> None:
        contract = InterfaceContract(name="fn", output_type="None")
        assert contract.input_types == {}
        assert contract.preconditions == []
        assert contract.postconditions == []


class TestDataFlowEdge:
    def test_construction(self) -> None:
        edge = DataFlowEdge(
            source_module="auth",
            target_module="api",
            data_type="AuthToken",
        )
        assert edge.source_module == "auth"
        assert edge.description == ""


class TestTestStrategy:
    def test_defaults(self) -> None:
        strategy = TestStrategy()
        assert strategy.unit_test_targets == []
        assert strategy.integration_test_targets == []
        assert strategy.edge_cases == []
        assert strategy.performance_benchmarks == []

    def test_full(self) -> None:
        strategy = TestStrategy(
            unit_test_targets=["create_user"],
            edge_cases=["empty email"],
        )
        assert len(strategy.unit_test_targets) == 1
        assert len(strategy.edge_cases) == 1


class TestModuleDesign:
    def test_minimal(self) -> None:
        design = ModuleDesign()
        assert design.work_item_id == ""
        assert design.module_structure == []
        assert design.complexity_estimate == "M"

    def test_full_construction(self) -> None:
        design = ModuleDesign(
            work_item_id="WI-001",
            module_structure=[
                ModuleSpec(file_path="src/api.py", responsibility="API routes"),
            ],
            interfaces=[
                InterfaceContract(name="get_users", output_type="list[User]"),
            ],
            data_flow=[
                DataFlowEdge(
                    source_module="db",
                    target_module="api",
                    data_type="list[User]",
                ),
            ],
            dependency_graph={"api": ["db"]},
            design_decisions=["Use REST over GraphQL"],
            complexity_estimate="L",
            test_strategy=TestStrategy(unit_test_targets=["get_users"]),
        )
        assert design.work_item_id == "WI-001"
        assert len(design.module_structure) == 1
        assert len(design.interfaces) == 1
        assert len(design.data_flow) == 1
        assert design.dependency_graph == {"api": ["db"]}
        assert design.complexity_estimate == "L"

    def test_frozen(self) -> None:
        design = ModuleDesign()
        with pytest.raises(ValidationError):
            design.work_item_id = "x"  # type: ignore[misc]

    def test_serialization_roundtrip(self) -> None:
        design = ModuleDesign(
            work_item_id="WI-002",
            module_structure=[
                ModuleSpec(file_path="a.py", responsibility="A"),
            ],
            test_strategy=TestStrategy(edge_cases=["null input"]),
        )
        data = design.model_dump()
        restored = ModuleDesign.model_validate(data)
        assert restored == design
