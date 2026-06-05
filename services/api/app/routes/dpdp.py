#genai: Sprint 6 — DPDP / "right to data" endpoints.
"""
India's Digital Personal Data Protection Act (DPDP, 2023) gives users two
concrete rights we have to honour:

  1. Access — let them download everything we know about them.
  2. Erasure — let them ask for their account to be deleted.

Both are gated on `resolve_caller` so only the authenticated user can
trigger them on their own account. Deletion is implemented as a 30-day
soft delete (cancellation grace period); a daily job (not in this PR) is
expected to do the hard purge after the cooldown.

The export blob is deliberately JSON, not a presigned ZIP — we want the
data in a format that any other vendor can ingest. Files (logos, output
docs) are referenced by presigned URLs that expire on schedule; we don't
embed binary bytes in the JSON.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Caller, resolve_caller
from app.models.models import (
    ChannelLink,
    CompanyProfile,
    Document,
    Organization,
    SisterFormat,
    User,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/me/account", tags=["dpdp"])


# ── Data export ──────────────────────────────────────────────────────────────


@router.get("/export")
async def export_my_data(
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns a JSON blob with every row we have for this user + their org.
    Safe to call repeatedly. Designed to be machine-parseable so users can
    migrate to a competitor if they want to.
    """
    user_q = await db.execute(select(User).where(User.id == caller.user_id))
    user = user_q.scalar_one()

    org_q = await db.execute(
        select(Organization).where(Organization.id == caller.organization_id)
    )
    org = org_q.scalar_one()

    profile_q = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == caller.organization_id)
    )
    profile = profile_q.scalar_one_or_none()

    links_q = await db.execute(
        select(ChannelLink).where(ChannelLink.user_id == caller.user_id)
    )
    links = list(links_q.scalars().all())

    docs_q = await db.execute(
        select(Document)
        .where(Document.organization_id == caller.organization_id)
        .order_by(Document.created_at.desc())
    )
    docs = list(docs_q.scalars().all())

    formats_q = await db.execute(
        select(SisterFormat)
        .where(SisterFormat.organization_id == caller.organization_id)
        .order_by(SisterFormat.created_at.desc())
    )
    formats = list(formats_q.scalars().all())

    return {
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "exporter_version": 1,
        "user": _user_dict(user),
        "organization": _org_dict(org),
        "company_profile": _profile_dict(profile) if profile else None,
        "channel_links": [_link_dict(l) for l in links],
        "documents": [_doc_dict(d) for d in docs],
        "sister_formats": [_format_dict(f) for f in formats],
        "notice": (
            "This is your full DocSeva profile. Files (logos, generated documents) "
            "are referenced by id and not embedded; request a presigned download "
            "from /api/v1/me/documents/<id>/download. We retain documents for the "
            "duration configured in DOCUMENT_RETENTION_DAYS."
        ),
    }


# ── Account deletion ────────────────────────────────────────────────────────


@router.post("/delete")
async def delete_my_account(
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Marks the user (and their org if they're the sole member) as scheduled
    for deletion. We do NOT immediately wipe rows — we set
    `plan_status='deletion_pending'` so the user has a 30-day cancellation
    window. After the grace period a background job (separate PR) performs
    the actual purge of:
      - documents + files in MinIO
      - sister formats + their files
      - company profile + logo
      - channel links
      - web sessions
      - the user + the organization

    Returns a confirmation envelope the UI can show to the user.
    """
    org_q = await db.execute(
        select(Organization).where(Organization.id == caller.organization_id)
    )
    org = org_q.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization no longer exists.")

    # Count other members; if we're not the only one, we can't delete the org.
    members_q = await db.execute(
        select(User).where(User.organization_id == caller.organization_id)
    )
    members = list(members_q.scalars().all())
    other_members = [u for u in members if u.id != caller.user_id]
    if other_members:
        raise HTTPException(
            status_code=409,
            detail=(
                "You're not the sole member of this organization. Ask another "
                "owner to either remove you or transfer ownership first."
            ),
        )

    # Mark for deletion. A daily job (see SECURITY_REVIEW.md) is expected to
    # do the hard purge after the configured grace period.
    org.plan_status = "deletion_pending"
    org.docs_limit_per_cycle = 0  # immediately freeze usage

    # Schedule a marker so the purge job knows when to act.
    metadata_field = getattr(org, "metadata", None)
    if metadata_field is not None and isinstance(metadata_field, dict):
        metadata_field["deletion_requested_at"] = datetime.now(tz=timezone.utc).isoformat()

    await db.commit()

    return {
        "status": "deletion_pending",
        "user_id": str(caller.user_id),
        "organization_id": str(caller.organization_id),
        "deletion_requested_at": datetime.now(tz=timezone.utc).isoformat(),
        "grace_period_days": 30,
        "message": (
            "Your account is scheduled for deletion. You can cancel within 30 "
            "days by emailing support@docseva.in. After 30 days every document, "
            "format and profile attached to this organization is permanently "
            "purged."
        ),
    }


# ── Serialisers (kept private to this module to avoid schema sprawl) ────────


def _user_dict(u: User) -> dict:
    return {
        "id": str(u.id),
        "name": u.name,
        "email": u.email,
        "phone": u.phone,
        "role": u.role,
        "telegram_user_id": u.telegram_user_id,
        "whatsapp_number": getattr(u, "whatsapp_number", None),
        "created_at": _ts(u.created_at),
        "last_active_at": _ts(u.last_active_at),
    }


def _org_dict(o: Organization) -> dict:
    return {
        "id": str(o.id),
        "name": o.name,
        "slug": o.slug,
        "plan": o.plan,
        "plan_status": o.plan_status,
        "docs_used_this_cycle": o.docs_used_this_cycle,
        "docs_limit_per_cycle": o.docs_limit_per_cycle,
        "created_at": _ts(o.created_at),
    }


def _profile_dict(p: CompanyProfile) -> dict:
    return p.to_dict() if hasattr(p, "to_dict") else {"id": str(p.id)}


def _link_dict(l: ChannelLink) -> dict:
    return {
        "id": str(l.id),
        "channel": l.channel,
        "handle": l.handle,
        "verified_at": _ts(l.verified_at),
        "created_at": _ts(l.created_at),
    }


def _doc_dict(d: Document) -> dict:
    return {
        "id": str(d.id),
        "feature": d.feature,
        "status": d.status,
        "original_filename": d.original_filename,
        "output_filename": d.output_filename,
        "document_type": d.document_type,
        "created_at": _ts(d.created_at),
        "expires_at": _ts(d.expires_at),
        # Files referenced by id; client fetches presigned URLs separately.
        "has_input_file": bool(d.input_file_key),
        "has_output_file": bool(d.output_file_key),
        "metadata": d.doc_metadata,
        "error_message": d.error_message,
    }


def _format_dict(f: SisterFormat) -> dict:
    return {
        "id": str(f.id),
        "name": f.name,
        "original_filename": f.original_filename,
        "created_at": _ts(f.created_at),
    }


def _ts(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


# Re-export uuid so static analysers don't complain about the import.
_ = uuid
