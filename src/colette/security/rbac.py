"""Role-based access control with four predefined roles (NFR-SEC-008).

Defines roles, permissions, and their mapping.  All data structures are
immutable; the permission matrix is a module-level constant.
"""

from __future__ import annotations

from enum import StrEnum

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class Role(StrEnum):
    """Colette user roles."""

    PROJECT_REQUESTOR = "project_requestor"
    TECHNICAL_REVIEWER = "technical_reviewer"
    SYSTEM_ADMINISTRATOR = "system_administrator"
    OBSERVER = "observer"


class Permission(StrEnum):
    """Fine-grained permissions granted to roles."""

    SUBMIT_PROJECT = "submit_project"
    VIEW_PROJECT = "view_project"
    APPROVE_DECISION = "approve_decision"
    REJECT_DECISION = "reject_decision"
    MODIFY_DECISION = "modify_decision"
    MANAGE_AGENTS = "manage_agents"
    MANAGE_CONFIG = "manage_config"
    VIEW_LOGS = "view_logs"
    VIEW_METRICS = "view_metrics"
    DOWNLOAD_ARTIFACTS = "download_artifacts"
    MANAGE_USERS = "manage_users"


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.PROJECT_REQUESTOR: frozenset(
        {
            Permission.SUBMIT_PROJECT,
            Permission.VIEW_PROJECT,
            Permission.DOWNLOAD_ARTIFACTS,
        }
    ),
    Role.TECHNICAL_REVIEWER: frozenset(
        {
            Permission.VIEW_PROJECT,
            Permission.APPROVE_DECISION,
            Permission.REJECT_DECISION,
            Permission.MODIFY_DECISION,
            Permission.VIEW_LOGS,
            Permission.VIEW_METRICS,
            Permission.DOWNLOAD_ARTIFACTS,
        }
    ),
    Role.SYSTEM_ADMINISTRATOR: frozenset(Permission),
    Role.OBSERVER: frozenset(
        {
            Permission.VIEW_PROJECT,
            Permission.VIEW_LOGS,
            Permission.VIEW_METRICS,
        }
    ),
}


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class PermissionDeniedError(PermissionError):
    """Raised when a role lacks the required permission."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def has_permission(role: Role, permission: Permission) -> bool:
    """Return ``True`` if *role* includes *permission*."""
    allowed = ROLE_PERMISSIONS.get(role, frozenset())
    return permission in allowed


def require_permission(role: Role, permission: Permission) -> None:
    """Raise ``PermissionDeniedError`` if *role* lacks *permission*."""
    if not has_permission(role, permission):
        msg = f"Role '{role.value}' does not have permission '{permission.value}'"
        raise PermissionDeniedError(msg)
