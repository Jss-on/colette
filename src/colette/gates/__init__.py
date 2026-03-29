"""Quality gate definitions and enforcement (FR-QG, Section 12)."""

from colette.gates.base import GateRegistry, QualityGate, evaluate_gate
from colette.gates.design_gate import DesignGate
from colette.gates.implementation_gate import ImplementationGate
from colette.gates.production_gate import ProductionGate
from colette.gates.requirements_gate import RequirementsGate
from colette.gates.staging_gate import StagingGate
from colette.gates.testing_gate import TestingGate


def create_default_registry() -> GateRegistry:
    """Build a ``GateRegistry`` with all six standard gates."""
    registry = GateRegistry()
    for gate in (
        RequirementsGate(),
        DesignGate(),
        ImplementationGate(),
        TestingGate(),
        StagingGate(),
        ProductionGate(),
    ):
        registry.register(gate)
    return registry


__all__ = [
    "DesignGate",
    "GateRegistry",
    "ImplementationGate",
    "ProductionGate",
    "QualityGate",
    "RequirementsGate",
    "StagingGate",
    "TestingGate",
    "create_default_registry",
    "evaluate_gate",
]
