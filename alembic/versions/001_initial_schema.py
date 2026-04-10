"""Initial schema: 12 tables per ENTERPRISE_DEV_SPEC §4.7.1

Revision ID: 001
Revises:
Create Date: 2026-04-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "chips", "chip_parameters", "documents", "document_images",
    "users", "bom_records", "bom_items", "knowledge_notes",
    "chip_alternatives", "design_rules", "errata", "query_audit_log",
]


def upgrade() -> None:
    # 1. chips
    op.create_table(
        "chips",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("part_number", sa.String(100), unique=True, nullable=False),
        sa.Column("manufacturer", sa.String(50), nullable=False),
        sa.Column("category", sa.String(50)),
        sa.Column("sub_category", sa.String(50)),
        sa.Column("family", sa.String(100)),
        sa.Column("package", sa.String(50)),
        sa.Column("pin_count", sa.Integer),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("datasheet_url", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_chips_part_number", "chips", ["part_number"])
    op.create_index("idx_chips_manufacturer", "chips", ["manufacturer"])
    op.create_index("idx_chips_category", "chips", ["category", "sub_category"])
    op.create_index("idx_chips_family", "chips", ["family"])

    # 2. chip_parameters
    op.create_table(
        "chip_parameters",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chip_id", sa.Integer, sa.ForeignKey("chips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parameter_name", sa.String(100), nullable=False),
        sa.Column("parameter_category", sa.String(50), nullable=False),
        sa.Column("min_value", sa.Float),
        sa.Column("typ_value", sa.Float),
        sa.Column("max_value", sa.Float),
        sa.Column("unit", sa.String(20)),
        sa.Column("condition", sa.Text),
        sa.Column("source_page", sa.Integer),
        sa.Column("source_table", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_params_chip_id", "chip_parameters", ["chip_id"])
    op.create_index("idx_params_name", "chip_parameters", ["parameter_name"])
    op.create_index("idx_params_chip_name", "chip_parameters", ["chip_id", "parameter_name"])

    # 3. documents
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("file_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.BigInteger),
        sa.Column("chip_id", sa.Integer, sa.ForeignKey("chips.id")),
        sa.Column("doc_type", sa.String(30), server_default="datasheet"),
        sa.Column("collection", sa.String(100), server_default="default"),
        sa.Column("source_type", sa.String(20), server_default="upload"),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("page_count", sa.Integer),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("celery_task_id", sa.String(100)),
    )
    op.create_index("idx_documents_hash", "documents", ["file_hash"])

    # 4. document_images
    op.create_table(
        "document_images",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_path", sa.Text, nullable=False),
        sa.Column("page_number", sa.Integer),
        sa.Column("image_type", sa.String(30)),
        sa.Column("caption", sa.Text),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_doc_images_document_id", "document_images", ["document_id"])

    # 5. users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("role", sa.String(20), nullable=False, server_default="viewer"),
        sa.Column("department", sa.String(100)),
        sa.Column("sso_provider", sa.String(30)),
        sa.Column("sso_sub", sa.String(255)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_users_sso", "users", ["sso_provider", "sso_sub"], unique=True,
                     postgresql_where=sa.text("sso_provider IS NOT NULL"))
    op.create_index("idx_users_role", "users", ["role"])

    # 6. bom_records
    op.create_table(
        "bom_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bom_name", sa.String(255), nullable=False),
        sa.Column("file_name", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("total_items", sa.Integer, server_default="0"),
        sa.Column("flagged_items", sa.Integer, server_default="0"),
        sa.Column("summary", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bom_records_user_id", "bom_records", ["user_id"])
    op.create_index("idx_bom_records_status", "bom_records", ["status"])

    # 7. bom_items
    op.create_table(
        "bom_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("bom_id", sa.Integer, sa.ForeignKey("bom_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.Column("part_number", sa.String(100), nullable=False),
        sa.Column("chip_id", sa.Integer, sa.ForeignKey("chips.id")),
        sa.Column("quantity", sa.Integer, server_default="1"),
        sa.Column("eol_flag", sa.Boolean, server_default="false"),
        sa.Column("param_conflict", sa.Boolean, server_default="false"),
        sa.Column("alt_chip_id", sa.Integer, sa.ForeignKey("chips.id")),
        sa.Column("review_note", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_bom_items_bom_id", "bom_items", ["bom_id"])
    op.create_index("idx_bom_items_part_number", "bom_items", ["part_number"])

    # 8. knowledge_notes
    op.create_table(
        "knowledge_notes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chip_id", sa.Integer, sa.ForeignKey("chips.id")),
        sa.Column("note_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255)),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", JSONB, server_default="'[]'"),
        sa.Column("is_public", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_knowledge_notes_user_id", "knowledge_notes", ["user_id"])
    op.create_index("idx_knowledge_notes_chip_id", "knowledge_notes", ["chip_id"])
    op.create_index("idx_knowledge_notes_tags", "knowledge_notes", ["tags"], postgresql_using="gin")

    # 9. chip_alternatives
    op.create_table(
        "chip_alternatives",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("original_id", sa.Integer, sa.ForeignKey("chips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alt_id", sa.Integer, sa.ForeignKey("chips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("compat_type", sa.String(30), nullable=False),
        sa.Column("compat_score", sa.Float),
        sa.Column("notes", sa.Text),
        sa.Column("verified", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_chip_alt_pair", "chip_alternatives", ["original_id", "alt_id"], unique=True)
    op.create_index("idx_chip_alt_original", "chip_alternatives", ["original_id"])

    # 10. design_rules
    op.create_table(
        "design_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chip_id", sa.Integer, sa.ForeignKey("chips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id")),
        sa.Column("rule_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="info"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("source_page", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_design_rules_chip_id", "design_rules", ["chip_id"])
    op.create_index("idx_design_rules_type", "design_rules", ["rule_type"])

    # 11. errata
    op.create_table(
        "errata",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("chip_id", sa.Integer, sa.ForeignKey("chips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id")),
        sa.Column("errata_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("workaround", sa.Text),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("affected_rev", sa.String(50)),
        sa.Column("source_page", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_errata_chip_id", "errata", ["chip_id"])
    op.create_index("idx_errata_errata_id", "errata", ["errata_id"])

    # 12. query_audit_log
    op.create_table(
        "query_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("trace_id", sa.String(36), nullable=False),
        sa.Column("query_text", sa.Text, nullable=False),
        sa.Column("intent", sa.String(50)),
        sa.Column("tools_used", JSONB, server_default="'[]'"),
        sa.Column("total_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("cache_hit", sa.Boolean, server_default="false"),
        sa.Column("status", sa.String(20), server_default="success"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_audit_user_id", "query_audit_log", ["user_id"])
    op.create_index("idx_audit_trace_id", "query_audit_log", ["trace_id"])
    op.create_index("idx_audit_created_at", "query_audit_log", ["created_at"])
    op.create_index("idx_audit_intent", "query_audit_log", ["intent"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
