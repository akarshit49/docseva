"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── organizations ────────────────────────────────────────────────────────
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), unique=True, nullable=True),
        sa.Column("plan", sa.Text(), server_default="free"),
        sa.Column("plan_status", sa.Text(), server_default="active"),
        sa.Column("plan_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("docs_used_this_cycle", sa.Integer(), server_default="0"),
        sa.Column("docs_limit_per_cycle", sa.Integer(), server_default="10"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), server_default="owner"),
        sa.Column("telegram_user_id", sa.Text(), unique=True, nullable=True),
        sa.Column("whatsapp_number", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="TRUE"),
        sa.Column("last_active_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"])

    # ── company_profiles ─────────────────────────────────────────────────────
    op.create_table(
        "company_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("pincode", sa.Text(), nullable=True),
        sa.Column("gstin", sa.Text(), nullable=True),
        sa.Column("pan", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("bank_name", sa.Text(), nullable=True),
        sa.Column("bank_account", sa.Text(), nullable=True),
        sa.Column("bank_ifsc", sa.Text(), nullable=True),
        sa.Column("logo_key", sa.Text(), nullable=True),   # MinIO key
        sa.Column("invoice_prefix", sa.Text(), server_default="INV"),
        sa.Column("invoice_counter", sa.Integer(), server_default="1"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )

    # ── documents ────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="completed"),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("output_filename", sa.Text(), nullable=True),
        sa.Column("output_file_key", sa.Text(), nullable=True),    # MinIO key
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"])
    op.create_index("ix_documents_created_at", "documents", ["created_at"])

    # ── usage_events ─────────────────────────────────────────────────────────
    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("feature", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), server_default="telegram"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("NOW()")),
    )


def downgrade() -> None:
    op.drop_table("usage_events")
    op.drop_table("documents")
    op.drop_table("company_profiles")
    op.drop_table("users")
    op.drop_table("organizations")
