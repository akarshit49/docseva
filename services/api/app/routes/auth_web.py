#genai: Sprint 1 / WS-A — Web auth routes (email OTP, JWT issuance, refresh, me).
"""
Web auth flow:

    POST /api/v1/auth/web/request-otp     { email }
    POST /api/v1/auth/web/verify-otp      { email, otp, [name, company_name] }
    POST /api/v1/auth/web/refresh         { refresh_token }
    POST /api/v1/auth/web/logout          (requires bearer)
    GET  /api/v1/auth/me                  (requires bearer or X-Bot-Token)

The first verify-otp for an unknown email auto-creates a User + Organization +
empty CompanyProfile + channel_links('web', email) row. This mirrors the
Telegram register-or-login UX but driven by an email handle.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.email import EmailMessage, send_email
from app.core.error_messages import raise_api_error
from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
)
from app.core.otp import otp_store
from app.core.security import Caller, resolve_caller
from app.core.storage import presigned_url
from app.models.models import (
    ChannelLink,
    CompanyProfile,
    Organization,
    User,
    WebSession,
)
from app.schemas.schemas import (
    CompanyProfileOut,
    MeResponse,
    OrganizationOut,
    UserOut,
    WebAuthResponse,
    WebOtpRequest,
    WebOtpVerify,
    WebRefreshRequest,
    WebTokens,
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


def _otp_email(email: str, otp: str) -> EmailMessage:
    return EmailMessage(
        to=email,
        subject="Your DocSeva sign-in code",
        text=(
            "Your DocSeva sign-in code is:\n\n"
            f"    {otp}\n\n"
            "It expires in 10 minutes. If you didn't request this, you can "
            "safely ignore this email."
        ),
        html=(
            "<p>Your DocSeva sign-in code is:</p>"
            f"<p style=\"font-size:28px;font-weight:600;letter-spacing:6px\">{otp}</p>"
            "<p>It expires in 10 minutes. If you didn't request this, you can "
            "safely ignore this email.</p>"
        ),
    )


@router.post("/web/request-otp", status_code=status.HTTP_204_NO_CONTENT)
async def request_otp(req: WebOtpRequest):
    """Issue a 6-digit OTP and email it. Always 204 — never leak which emails exist."""
    otp = otp_store.issue(req.email)
    try:
        send_email(_otp_email(req.email, otp))
    except Exception:
        # Email delivery failure shouldn't 5xx the request; the OTP is still
        # logged on the server and can be looked up if needed during dev.
        pass
    return None


@router.post("/web/verify-otp", response_model=WebAuthResponse)
async def verify_otp(
    req: WebOtpVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Verify OTP → create-or-fetch user → return access + refresh tokens."""
    if not otp_store.verify(req.email, req.otp):
        raise_api_error("E009", details={"reason": "Invalid or expired OTP."})

    # Find an existing user by email.
    user_q = await db.execute(select(User).where(User.email == req.email))
    user = user_q.scalar_one_or_none()
    is_new = False

    if not user:
        # First-time login: provision an org + user + empty profile.
        company_name = (req.company_name or "").strip() or req.email.split("@")[0]
        display_name = (req.name or "").strip() or req.email.split("@")[0]

        base_slug = _slug(company_name) or "team"
        slug = base_slug
        counter = 1
        while True:
            exists = await db.execute(
                select(Organization).where(Organization.slug == slug)
            )
            if not exists.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        plan = "free"
        org = Organization(
            name=company_name,
            slug=slug,
            plan=plan,
            plan_status="active",
            docs_limit_per_cycle=_PLAN_LIMITS[plan],
        )
        db.add(org)
        await db.flush()

        user = User(
            organization_id=org.id,
            name=display_name,
            email=req.email,
            role="owner",
            last_active_at=datetime.now(tz=timezone.utc),
        )
        db.add(user)
        await db.flush()

        profile = CompanyProfile(
            organization_id=org.id,
            display_name=company_name,
            email=req.email,
        )
        db.add(profile)

        # Bind the email as a 'web' channel handle.
        db.add(
            ChannelLink(
                user_id=user.id,
                organization_id=org.id,
                channel="web",
                handle=req.email,
                verified_at=datetime.now(tz=timezone.utc),
            )
        )
        is_new = True
    else:
        user.last_active_at = datetime.now(tz=timezone.utc)
        # Ensure a 'web' channel-link exists for this user (older accounts may
        # have signed up via Telegram first and now be linking the web).
        existing = await db.execute(
            select(ChannelLink).where(
                ChannelLink.channel == "web",
                ChannelLink.handle == req.email,
            )
        )
        if not existing.scalar_one_or_none():
            db.add(
                ChannelLink(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    channel="web",
                    handle=req.email,
                    verified_at=datetime.now(tz=timezone.utc),
                )
            )

    # Issue tokens.
    org_q = await db.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    org = org_q.scalar_one()

    access = create_access_token(user_id=user.id, org_id=org.id)
    raw_refresh, refresh_hash, refresh_exp = create_refresh_token()

    db.add(
        WebSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            user_agent=request.headers.get("user-agent"),
            ip=request.client.host if request.client else None,
            expires_at=refresh_exp,
        )
    )
    await db.commit()
    await db.refresh(user)
    await db.refresh(org)

    return WebAuthResponse(
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(org),
        tokens=WebTokens(access_token=access, refresh_token=raw_refresh),
        is_new=is_new,
    )


@router.post("/web/refresh", response_model=WebTokens)
async def refresh_session(req: WebRefreshRequest, db: AsyncSession = Depends(get_db)):
    """Swap a valid refresh token for a fresh access (and rotate refresh)."""
    h = hash_refresh_token(req.refresh_token)
    q = await db.execute(
        select(WebSession).where(WebSession.refresh_token_hash == h)
    )
    session = q.scalar_one_or_none()
    if not session or session.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    now = datetime.now(tz=timezone.utc)
    if session.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=401, detail="Refresh token expired.")

    user_q = await db.execute(select(User).where(User.id == session.user_id))
    user = user_q.scalar_one()

    # Rotate: revoke this session, mint a new one.
    session.revoked_at = now
    raw_refresh, refresh_hash, refresh_exp = create_refresh_token()
    db.add(
        WebSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            user_agent=session.user_agent,
            ip=session.ip,
            expires_at=refresh_exp,
        )
    )
    await db.commit()

    return WebTokens(
        access_token=create_access_token(
            user_id=user.id, org_id=user.organization_id
        ),
        refresh_token=raw_refresh,
    )


@router.post("/web/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    req: WebRefreshRequest,
    db: AsyncSession = Depends(get_db),
    caller: Caller = Depends(resolve_caller),
):
    """Revoke the refresh token. Access tokens expire on their own (≤ 1h)."""
    if caller.channel != "web":
        raise HTTPException(status_code=403, detail="Not a web session.")
    h = hash_refresh_token(req.refresh_token)
    q = await db.execute(
        select(WebSession).where(
            WebSession.refresh_token_hash == h,
            WebSession.user_id == caller.user_id,
        )
    )
    session = q.scalar_one_or_none()
    if session:
        session.revoked_at = datetime.now(tz=timezone.utc)
        await db.commit()
    return None


@router.get("/me", response_model=MeResponse)
async def me(
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    """Return the canonical user + org + profile for any authenticated caller."""
    user_q = await db.execute(select(User).where(User.id == caller.user_id))
    user = user_q.scalar_one()
    org_q = await db.execute(
        select(Organization).where(Organization.id == caller.organization_id)
    )
    org = org_q.scalar_one()
    prof_q = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.organization_id == caller.organization_id
        )
    )
    profile = prof_q.scalar_one_or_none()
    profile_out: CompanyProfileOut | None = None
    if profile:
        profile_out = CompanyProfileOut.model_validate(profile)
        if profile.logo_key:
            try:
                profile_out.logo_url = presigned_url(
                    settings.minio_bucket_assets, profile.logo_key
                )
            except Exception:
                profile_out.logo_url = None

    return MeResponse(
        user=UserOut.model_validate(user),
        organization=OrganizationOut.model_validate(org),
        company_profile=profile_out,
    )
