"""Typed Pydantic handoff schemas for inter-stage communication (FR-ORC-020)."""

from colette.schemas.base import HandoffSchema
from colette.schemas.deployment import DeploymentToMonitoringHandoff
from colette.schemas.design import DesignToImplementationHandoff
from colette.schemas.implementation import ImplementationToTestingHandoff
from colette.schemas.requirements import RequirementsToDesignHandoff
from colette.schemas.testing import TestingToDeploymentHandoff

__all__ = [
    "DeploymentToMonitoringHandoff",
    "DesignToImplementationHandoff",
    "HandoffSchema",
    "ImplementationToTestingHandoff",
    "RequirementsToDesignHandoff",
    "TestingToDeploymentHandoff",
]
