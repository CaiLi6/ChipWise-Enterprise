"""Add metadata JSONB column to documents and unique index on chip_parameters.

Phase A — GraphRAG ingestion wiring (2026-04-23).

Revision ID: 002_kg_metadata
Revises: 001_initial_schema
Create Date: 2026-04-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_kg_metadata"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_chip_parameters_chip_name "
        "ON chip_parameters (chip_id, parameter_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_chip_parameters_chip_name")
    op.drop_column("documents", "metadata")
