#genai: Auth routes — register/login via Telegram user ID, quota check.
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_bot_token
from app.models.models import ChannelLink, CompanyProfile, Organization, User
from app.schemas.schemas import (
    AuthResponse,
    ChannelRegisterRequest,
    CompanyProfileOut,
    OrganizationOut,
    QuotaStatus,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_PLAN_LIMITS = {
    "free": settings.free_plan_docs_per_month,
    "starter": settings.starter_plan_docs_per_month,
    "pro": settings.pro_plan_docs_per_month,
    "business": settings.business_plan_docs_per_month,
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]


@router.post("/register", response_model=AuthResponse, dependencies=[Depends(verify_bot_token)])
async def register_or_login(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Idempotent register/login — call this every time a user starts a new session.
    Returns existing user if telegram_user_id already exists, otherwise creates one.
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.telegram_user_id == req.telegram_user_id)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # Update last active
        existing_user.last_active_at = datetime.now(tz=timezone.utc)
        await db.commit()

        org_result = await db.execute(
            select(Organization).where(Organization.id == existing_user.organization_id)
        )
        org = org_result.scalar_one()

        return AuthResponse(
            user=UserOut.model_validate(existing_user),
            organization=OrganizationOut.model_validate(org),
            is_new=False,
        )

    # New user — create org + user + empty company profile
    base_slug = _slug(req.company_name)
    # Ensure slug uniqueness
    slug = base_slug
    counter = 1
    while True:
        exists = await db.execute(select(Organization).where(Organization.id.isnot(None), Organization.slug == slug))
        if not exists.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    plan = "free"
    org = Organization(
        name=req.company_name,
        slug=slug,
        plan=plan,
        plan_status="active",
        docs_limit_per_cycle=_PLAN_LIMITS[plan],
    )
    db.add(org)
    await db.flush()  # get org.id

    user = User(
        organization_id=org.id,
        name=req.name,
        email=req.email,
        phone=req.phone,
        telegram_user_id=req.telegram_user_id,
        role="owner",
        last_active_at=datetime.now(tz=timezone.utc),
    )
    db.add(user)

    profile = CompanyProfile(
        organization_id=org.id,
        display_name=req.company_name,
        phone=req.phone,
        email=req.email,
    )
    db.add(profile)

    await db.commit()
    await db.refresh(user)
    await db.refresh(org)

    return AuthResponse(
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(org),
        is_new=True,
    )


#genai: Sprint 5 / WS-E — channel-aware register/login for ALL bot adapters.
#       Same semantics as `/register` but keyed by `(channel, handle)` via the
#       `ChannelLink` table so WhatsApp, future Slack, etc. work without
#       schema changes.
_VALID_CHANNELS = {"telegram", "whatsapp", "email"}


@router.post(
    "/register-channel",
    response_model=AuthResponse,
    dependencies=[Depends(verify_bot_token)],
)
async def register_channel(
    req: ChannelRegisterRequest, db: AsyncSession = Depends(get_db)
):
    if req.channel not in _VALID_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported channel: {req.channel}. Must be one of {sorted(_VALID_CHANNELS)}.",
        )

    handle = req.handle.strip()
    if not handle:
        raise HTTPException(status_code=400, detail="handle is required.")

    # Look up an existing link (this is the fast path on every bot message).
    link_q = await db.execute(
        select(ChannelLink).where(
            ChannelLink.channel == req.channel,
            ChannelLink.handle == handle,
        )
    )
    existing_link = link_q.scalar_one_or_none()

    if existing_link:
        user_q = await db.execute(
            select(User).where(User.id == existing_link.user_id)
        )
        existing_user = user_q.scalar_one()
        existing_user.last_active_at = datetime.now(tz=timezone.utc)
        await db.commit()

        org_q = await db.execute(
            select(Organization).where(Organization.id == existing_user.organization_id)
        )
        org = org_q.scalar_one()
        return AuthResponse(
            user=UserOut.model_validate(existing_user),
            organization=OrganizationOut.model_validate(org),
            is_new=False,
        )

    # Provision: org + user + channel link + empty profile.
    base_slug = _slug(req.company_name)
    slug = base_slug
    counter = 1
    while True:
        slug_check = await db.execute(
            select(Organization).where(Organization.slug == slug)
        )
        if not slug_check.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    plan = "free"
    org = Organization(
        name=req.company_name,
        slug=slug,
        plan=plan,
        plan_status="active",
        docs_limit_per_cycle=_PLAN_LIMITS[plan],
    )
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        name=req.name,
        email=req.email,
        phone=req.phone,
        # Keep `telegram_user_id` populated when the channel is telegram so
        # legacy URL-keyed routes keep working for backward compat (KI from §16).
        telegram_user_id=handle if req.channel == "telegram" else None,
        role="owner",
        last_active_at=datetime.now(tz=timezone.utc),
    )
    db.add(user)
    await db.flush()

    link = ChannelLink(
        user_id=user.id,
        organization_id=org.id,
        channel=req.channel,
        handle=handle,
        verified_at=datetime.now(tz=timezone.utc) if req.verified else None,
    )
    db.add(link)

    profile = CompanyProfile(
        organization_id=org.id,
        display_name=req.company_name,
        phone=req.phone,
        email=req.email,
    )
    db.add(profile)

    await db.commit()
    await db.refresh(user)
    await db.refresh(org)

    return AuthResponse(
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(org),
        is_new=True,
    )


@router.get("/quota/{telegram_user_id}", response_model=QuotaStatus, dependencies=[Depends(verify_bot_token)])
async def get_quota(telegram_user_id: str, db: AsyncSession = Depends(get_db)):
    """Check remaining document quota for a user."""
    result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org_result = await db.execute(select(Organization).where(Organization.id == user.organization_id))
    org = org_result.scalar_one()

    limit = _PLAN_LIMITS.get(org.plan, settings.free_plan_docs_per_month)
    used = org.docs_used_this_cycle
    remaining = max(0, limit - used)

    return QuotaStatus(
        plan=org.plan,
        docs_used=used,
        docs_limit=limit,
        docs_remaining=remaining,
        quota_ok=(remaining > 0),
    )


@router.post("/quota/{telegram_user_id}/increment", dependencies=[Depends(verify_bot_token)])
async def increment_quota(telegram_user_id: str, db: AsyncSession = Depends(get_db)):
    """Increment docs_used_this_cycle by 1. Called after successful document processing."""
    result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    org_result = await db.execute(select(Organization).where(Organization.id == user.organization_id))
    org = org_result.scalar_one()
    org.docs_used_this_cycle += 1
    await db.commit()
    return {"docs_used": org.docs_used_this_cycle}
