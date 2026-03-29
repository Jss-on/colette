# Schemas

Typed Pydantic handoff schemas for inter-stage communication (FR-ORC-020).

## Base Schema

::: colette.schemas.base.HandoffSchema

## Common Models

::: colette.schemas.common

## Agent Configuration

::: colette.schemas.agent_config

## Stage Handoffs

### Requirements -> Design

::: colette.schemas.requirements.RequirementsToDesignHandoff

### Design -> Implementation

::: colette.schemas.design.DesignToImplementationHandoff

::: colette.schemas.design.ImplementationTask

### Implementation -> Testing

::: colette.schemas.implementation.ImplementationToTestingHandoff

### Testing -> Deployment

::: colette.schemas.testing.TestingToDeploymentHandoff

### Deployment -> Monitoring

::: colette.schemas.deployment.DeploymentToMonitoringHandoff
