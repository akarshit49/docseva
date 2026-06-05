"""multichannel — channel_links, web_sessions, drafts, users.email unique

Revision ID: 004
Revises: 003
Create Date: 2026-06-01

#genai: Sprint 1 / WS-A — unified identity (one User, many channel handles).
Adds ChannelLink, WebSession, Draft tables; makes users.email unique to support
email-based web login (OTP).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users.email uniqueness ────────────────────────────────────────────────
    # Existing rows may have NULL email — partial unique index would be ideal but
    # we keep it portable: NULLs are NOT considered duplicates by Postgres for
    # UNIQUE constraints, which is exactly the behaviour we want.
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── channel_links ────────────────────────────────────────────────────────
    op.create_table(
        "channel_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("handle", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("channel", "handle", name="uq_channel_handle"),
    )
    op.create_index("ix_channel_links_user_id", "channel_links", ["user_id"])
    op.create_index("ix_channel_links_org_id", "channel_links", ["organization_id"])

    # Back-fill: every existing telegram_user_id becomes a channel_link row.
    op.execute(
        """
        INSERT INTO channel_links (user_id, organization_id, channel, handle, verified_at, created_at)
        SELECT id, organization_id, 'telegram', telegram_user_id, NOW(), created_at
          FROM users
         WHERE telegram_user_id IS NOT NULL
        ON CONFLICT (channel, handle) DO NOTHING
        """
    )

    # ── web_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        "web_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_web_sessions_refresh_token_hash",
        "web_sessions",
        ["refresh_token_hash"],
    )
    op.create_index("ix_web_sessions_user_id", "web_sessions", ["user_id"])

    # ── drafts ───────────────────────────────────────────────────────────────
    op.create_table(
        "drafts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("feature", sa.Text(), nullable=False),
        sa.Column("state", postgresql.JSONB(), server_default="{}"),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_drafts_user_id", "drafts", ["user_id"])
    op.create_index("ix_drafts_feature", "drafts", ["feature"])


def downgrade() -> None:
    op.drop_index("ix_drafts_feature", table_name="drafts")
    op.drop_index("ix_drafts_user_id", table_name="drafts")
    op.drop_table("drafts")

    op.drop_index("ix_web_sessions_user_id", table_name="web_sessions")
    op.drop_index(
        "ix_web_sessions_refresh_token_hash", table_name="web_sessions"
    )
    op.drop_table("web_sessions")

    op.drop_index("ix_channel_links_org_id", table_name="channel_links")
    op.drop_index("ix_channel_links_user_id", table_name="channel_links")
    op.drop_table("channel_links")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_constraint("uq_users_email", "users", type_="unique")
