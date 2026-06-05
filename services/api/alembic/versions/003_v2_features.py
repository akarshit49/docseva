"""v2 features — PO/Quotation counters, input_file_key, source_document_id, document_type

Revision ID: 003
Revises: 002
Create Date: 2026-05-31

#genai: Phase 2 / Week 2 — WS-3 (Create from scratch), WS-4 (PO), WS-12 (durability), WS-6 (chaining)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── company_profiles: PO + Quotation counters ─────────────────────────────
    op.add_column(
        "company_profiles",
        sa.Column("po_prefix", sa.Text(), server_default="PO", nullable=False),
    )
    op.add_column(
        "company_profiles",
        sa.Column("po_counter", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "company_profiles",
        sa.Column("quotation_prefix", sa.Text(), server_default="QT", nullable=False),
    )
    op.add_column(
        "company_profiles",
        sa.Column("quotation_counter", sa.Integer(), server_default="1", nullable=False),
    )

    # ── documents: store original input + chaining + type ─────────────────────
    op.add_column(
        "documents",
        sa.Column("input_file_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_documents_source_document_id",
        "documents",
        "documents",
        ["source_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "documents",
        sa.Column("document_type", sa.Text(), nullable=True),
    )
    op.create_index("ix_documents_document_type", "documents", ["document_type"])


def downgrade() -> None:
    op.drop_index("ix_documents_document_type", table_name="documents")
    op.drop_column("documents", "document_type")
    op.drop_constraint("fk_documents_source_document_id", "documents", type_="foreignkey")
    op.drop_column("documents", "source_document_id")
    op.drop_column("documents", "input_file_key")

    op.drop_column("company_profiles", "quotation_counter")
    op.drop_column("company_profiles", "quotation_prefix")
    op.drop_column("company_profiles", "po_counter")
    op.drop_column("company_profiles", "po_prefix")
