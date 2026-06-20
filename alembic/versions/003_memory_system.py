"""Add agent memory episodes, procedures, and governed memories.

Revision ID: 003_memory_system
Revises: 002_kg_metadata
Create Date: 2026-06-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "003_memory_system"
down_revision = "002_kg_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "memory_episodes",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_key", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("rewritten_query", sa.Text),
        sa.Column("tools_used", JSONB, server_default="[]"),
        sa.Column("citations", JSONB, server_default="[]"),
        sa.Column("grounding", JSONB, server_default="{}"),
        sa.Column("eval_metrics", JSONB, server_default="{}"),
        sa.Column("answer_preview", sa.Text),
        sa.Column("outcome", sa.String(32), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_memory_episodes_user", "memory_episodes", ["user_key"])
    op.create_index("idx_memory_episodes_session", "memory_episodes", ["user_key", "session_id"])
    op.create_index("idx_memory_episodes_trace", "memory_episodes", ["trace_id"])
    op.create_index("idx_memory_episodes_created", "memory_episodes", ["created_at"])
    op.create_index("idx_memory_episodes_outcome", "memory_episodes", ["outcome"])

    op.create_table(
        "memory_procedures",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("intent", sa.String(64), nullable=False),
        sa.Column("trigger_patterns", JSONB, server_default="[]"),
        sa.Column("recommended_tools", JSONB, server_default="[]"),
        sa.Column("stop_rules", JSONB, server_default="[]"),
        sa.Column("success_count", sa.Integer, server_default="0"),
        sa.Column("failure_count", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_memory_procedures_intent", "memory_procedures", ["intent"])
    op.create_index("idx_memory_procedures_status", "memory_procedures", ["status"])

    op.create_table(
        "memory_records",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("owner_key", sa.String(128)),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", JSONB, server_default="[]"),
        sa.Column("source", sa.String(64), nullable=False, server_default="manual"),
        sa.Column("source_id", sa.String(128)),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("metadata", JSONB, server_default="{}"),
        sa.Column("use_count", sa.Integer, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_memory_records_scope_owner", "memory_records", ["scope", "owner_key"])
    op.create_index("idx_memory_records_kind", "memory_records", ["kind"])
    op.create_index("idx_memory_records_status", "memory_records", ["status"])
    op.create_index("idx_memory_records_source", "memory_records", ["source", "source_id"])


def downgrade() -> None:
    op.drop_table("memory_records")
    op.drop_table("memory_procedures")
    op.drop_table("memory_episodes")
