"""Module design schemas for architect agent output (Phase 2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ModuleSpec(BaseModel):
    """Specification for a single module/file in the design."""

    model_config = ConfigDict(frozen=True)

    file_path: str = Field(description="Relative file path for this module.")
    responsibility: str = Field(description="Single-responsibility description.")
    public_api: list[str] = Field(
        default_factory=list,
        description="Exported function/class names.",
    )


class InterfaceContract(BaseModel):
    """Contract for a public interface between modules."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Function or method name.")
    input_types: dict[str, str] = Field(
        default_factory=dict,
        description="Parameter name -> type string.",
    )
    output_type: str = Field(description="Return type string.")
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)


class DataFlowEdge(BaseModel):
    """A data dependency between two modules."""

    model_config = ConfigDict(frozen=True)

    source_module: str = Field(description="Module that produces the data.")
    target_module: str = Field(description="Module that consumes the data.")
    data_type: str = Field(description="Type of data flowing between modules.")
    description: str = Field(default="")


class TestStrategy(BaseModel):
    """Testing strategy derived from the module design."""

    model_config = ConfigDict(frozen=True)

    unit_test_targets: list[str] = Field(
        default_factory=list,
        description="Functions/classes requiring unit tests.",
    )
    integration_test_targets: list[str] = Field(
        default_factory=list,
        description="Module boundaries requiring integration tests.",
    )
    edge_cases: list[str] = Field(
        default_factory=list,
        description="Identified edge cases to cover.",
    )
    performance_benchmarks: list[str] = Field(
        default_factory=list,
        description="Performance-critical paths to benchmark.",
    )


class ModuleDesign(BaseModel):
    """Complete module-level design produced by the architect agent."""

    model_config = ConfigDict(frozen=True)

    work_item_id: str = Field(
        default="",
        description="ID of the work item this design addresses.",
    )
    module_structure: list[ModuleSpec] = Field(default_factory=list)
    interfaces: list[InterfaceContract] = Field(default_factory=list)
    data_flow: list[DataFlowEdge] = Field(default_factory=list)
    dependency_graph: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Module -> list of modules it depends on.",
    )
    design_decisions: list[str] = Field(default_factory=list)
    complexity_estimate: str = Field(
        default="M",
        description="S, M, L, or XL complexity estimate.",
    )
    test_strategy: TestStrategy = Field(default_factory=TestStrategy)
