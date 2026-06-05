#genai: Company profile routes — CRUD + logo upload.
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_bot_token
from app.core.storage import presigned_url, upload_file
from app.models.models import CompanyProfile, Organization, User
from app.schemas.schemas import (
    CompanyProfileOut,
    CompanyProfileUpdate,
    IncrementCounterRequest,
    IncrementCounterResponse,
)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


async def _get_user_and_profile(telegram_user_id: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    prof_result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == user.organization_id)
    )
    profile = prof_result.scalar_one_or_none()
    return user, profile


@router.get("/{telegram_user_id}", response_model=CompanyProfileOut, dependencies=[Depends(verify_bot_token)])
async def get_profile(telegram_user_id: str, db: AsyncSession = Depends(get_db)):
    _, profile = await _get_user_and_profile(telegram_user_id, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Company profile not found.")

    out = CompanyProfileOut.model_validate(profile)
    if profile.logo_key:
        try:
            out.logo_url = presigned_url(settings.minio_bucket_assets, profile.logo_key)
        except Exception:
            out.logo_url = None
    return out


@router.put("/{telegram_user_id}", response_model=CompanyProfileOut, dependencies=[Depends(verify_bot_token)])
async def update_profile(
    telegram_user_id: str,
    data: CompanyProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    user, profile = await _get_user_and_profile(telegram_user_id, db)
    if not profile:
        # Create one if missing
        profile = CompanyProfile(organization_id=user.organization_id)
        db.add(profile)

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(profile)

    out = CompanyProfileOut.model_validate(profile)
    if profile.logo_key:
        try:
            out.logo_url = presigned_url(settings.minio_bucket_assets, profile.logo_key)
        except Exception:
            out.logo_url = None
    return out


@router.post("/{telegram_user_id}/logo", dependencies=[Depends(verify_bot_token)])
async def upload_logo(
    telegram_user_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload company logo PNG. Stored in MinIO assets bucket."""
    user, profile = await _get_user_and_profile(telegram_user_id, db)
    if not profile:
        raise HTTPException(status_code=404, detail="Company profile not found.")

    if file.content_type not in ("image/png", "image/jpeg", "image/jpg", "image/webp"):
        raise HTTPException(status_code=400, detail="Only PNG/JPG/WEBP logos are accepted.")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "png"
    key = f"logos/{user.organization_id}/logo.{ext}"
    data = await file.read()
    upload_file(settings.minio_bucket_assets, key, data, file.content_type)

    profile.logo_key = key
    profile.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()

    url = presigned_url(settings.minio_bucket_assets, key)
    return {"logo_key": key, "logo_url": url}


#genai: WS-3 / 17.5 — atomic counter increment for invoice/po/quotation numbering
_COUNTER_FIELDS = {
    "invoice": "invoice_counter",
    "po": "po_counter",
    "quotation": "quotation_counter",
}


@router.post(
    "/{telegram_user_id}/increment-counter",
    response_model=IncrementCounterResponse,
    dependencies=[Depends(verify_bot_token)],
)
async def increment_counter(
    telegram_user_id: str,
    req: IncrementCounterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Atomically increment a counter (invoice, po, or quotation) and return new value."""
    if req.counter_type not in _COUNTER_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid counter_type. Must be one of: {sorted(_COUNTER_FIELDS)}",
        )

    user, profile = await _get_user_and_profile(telegram_user_id, db)
    if not profile:
        profile = CompanyProfile(organization_id=user.organization_id)
        db.add(profile)
        await db.flush()

    field = _COUNTER_FIELDS[req.counter_type]
    new_value = (getattr(profile, field) or 0) + 1
    setattr(profile, field, new_value)
    profile.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()

    return IncrementCounterResponse(counter_type=req.counter_type, new_value=new_value)
