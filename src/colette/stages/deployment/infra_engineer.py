"""Infrastructure Engineer agent — Docker, K8s, secrets, TLS (FR-DEP-001/002/004/007/009/010)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel, Field

from colette.llm.structured import invoke_structured
from colette.schemas.agent_config import ModelTier
from colette.schemas.common import GeneratedFile
from colette.stages.deployment.prompts import INFRA_ENGINEER_SYSTEM_PROMPT

if TYPE_CHECKING:
    from colette.config import Settings

logger = structlog.get_logger(__name__)


class InfraResult(BaseModel, frozen=True):
    """Structured output from the Infrastructure Engineer agent."""

    files: list[GeneratedFile] = Field(default_factory=list)
    docker_images: list[str] = Field(
        default_factory=list,
        description="Docker image:tag strings (e.g. 'app-backend:latest').",
    )
    has_kubernetes: bool = Field(
        default=False,
        description="Whether Kubernetes manifests were generated.",
    )
    deployment_strategy: str = Field(
        default="rolling",
        description="Deployment strategy: rolling, blue_green, or canary.",
    )
    secrets_strategy: str = Field(
        default="",
        description="How secrets are managed (e.g. 'sealed-secrets', 'external-secrets').",
    )
    tls_configured: bool = Field(
        default=False,
        description="Whether TLS/cert-manager is configured.",
    )
    health_check_paths: list[str] = Field(
        default_factory=list,
        description="Health check endpoint paths (e.g. '/health', '/readyz').",
    )
    notes: str = Field(default="", description="Implementation notes or caveats.")


async def run_infra_engineer(
    deployment_context: str,
    *,
    settings: Settings,
) -> InfraResult:
    """Generate infrastructure configurations (FR-DEP-001/002/004/007/009/010).

    Uses the EXECUTION model tier (Sonnet) for IaC generation.
    """
    logger.info("infra_engineer.start")

    result = await invoke_structured(
        system_prompt=INFRA_ENGINEER_SYSTEM_PROMPT,
        user_content=f"Project Architecture:\n\n{deployment_context}",
        output_type=InfraResult,
        settings=settings,
        model_tier=ModelTier.VALIDATION,
    )

    logger.info(
        "infra_engineer.complete",
        files=len(result.files),
        images=len(result.docker_images),
        k8s=result.has_kubernetes,
        strategy=result.deployment_strategy,
    )
    return result
