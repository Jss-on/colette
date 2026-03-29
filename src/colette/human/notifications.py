"""Notification dispatch for approval requests (FR-HIL-005)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import structlog

from colette.config import Settings
from colette.human.models import ApprovalRequest

logger = structlog.get_logger()


@runtime_checkable
class NotificationChannel(Protocol):
    """Protocol for pluggable notification backends."""

    async def send(self, request: ApprovalRequest) -> bool: ...


class InAppChannel:
    """Logs the notification — concrete UI delivery is Phase 8."""

    async def send(self, request: ApprovalRequest) -> bool:
        logger.info(
            "notification.in_app",
            request_id=request.request_id,
            stage=request.stage,
            tier=request.tier.value,
        )
        return True


class SlackChannel:
    """Posts an approval notification to a Slack webhook."""

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    async def send(self, request: ApprovalRequest) -> bool:
        if not self._url:
            return False
        try:
            import httpx

            payload = {
                "text": (
                    f":rotating_light: *Approval Required* ({request.tier.value})\n"
                    f"Stage: {request.stage} | Project: {request.project_id}\n"
                    f"{request.context_summary}"
                ),
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(self._url, json=payload, timeout=10.0)
            return resp.is_success
        except Exception:
            logger.exception("notification.slack_error", request_id=request.request_id)
            return False


class EmailChannel:
    """Stub — concrete SMTP delivery deferred to Phase 8."""

    async def send(self, request: ApprovalRequest) -> bool:
        logger.info(
            "notification.email_stub",
            request_id=request.request_id,
            stage=request.stage,
        )
        return True


def _build_channels(settings: Settings) -> list[NotificationChannel]:
    """Instantiate channels from settings."""
    channels: list[NotificationChannel] = []
    for name in settings.notification_channels:
        if name == "in_app":
            channels.append(InAppChannel())
        elif name == "slack" and settings.notification_slack_webhook:
            channels.append(SlackChannel(settings.notification_slack_webhook))
        elif name == "email":
            channels.append(EmailChannel())
    return channels


async def notify_reviewers(request: ApprovalRequest, settings: Settings) -> list[bool]:
    """Dispatch an approval notification to all configured channels."""
    channels = _build_channels(settings)
    results: list[bool] = []
    for ch in channels:
        ok = await ch.send(request)
        results.append(ok)
    return results
