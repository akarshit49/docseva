"""
#genai: Sprint 1 — ORM + migration sanity for the multichannel data model.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_orm_has_new_tables():
    from app.models.models import ChannelLink, Draft, WebSession

    cl = {c.name for c in ChannelLink.__table__.columns}
    assert {"user_id", "organization_id", "channel", "handle"} <= cl

    ws = {c.name for c in WebSession.__table__.columns}
    assert {"user_id", "refresh_token_hash", "expires_at", "revoked_at"} <= ws

    dr = {c.name for c in Draft.__table__.columns}
    assert {"user_id", "channel", "feature", "state"} <= dr


def test_channel_link_unique_constraint():
    from app.models.models import ChannelLink

    constraints = [
        c.name
        for c in ChannelLink.__table__.constraints
        if c.name and "channel_handle" in c.name
    ]
    assert constraints, "Expected uq_channel_handle unique constraint."


def test_migration_004_has_correct_metadata():
    """Source-level checks (DB upgrade is exercised at deploy)."""
    mig_path = ROOT / "alembic" / "versions" / "004_multichannel.py"
    assert mig_path.exists()
    src = mig_path.read_text()
    assert 'revision = "004"' in src
    assert 'down_revision = "003"' in src
    assert "def upgrade()" in src and "def downgrade()" in src
    assert "channel_links" in src
    assert "web_sessions" in src
    assert "drafts" in src
    assert "uq_channel_handle" in src
    # Back-fill of existing telegram_user_id values.
    assert "INSERT INTO channel_links" in src
