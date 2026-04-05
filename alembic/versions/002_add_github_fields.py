"""Add repo_url and repo_name to projects for GitHub integration.

Revision ID: 002
Revises: 001
Create Date: 2026-04-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("repo_url", sa.String(1024), nullable=True))
    op.add_column("projects", sa.Column("repo_name", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "repo_name")
    op.drop_column("projects", "repo_url")
