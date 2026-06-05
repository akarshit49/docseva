#genai: Sister format routes — store and retrieve user-uploaded quotation format templates.
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_bot_token
from app.core.storage import delete_file, download_file, upload_file
from app.models.models import SisterFormat, User
from app.schemas.schemas import SisterFormatOut

router = APIRouter(prefix="/api/v1/sister-formats", tags=["sister-formats"])

_MAX_FORMATS = 10
_ALLOWED_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}


async def _get_org_id(telegram_user_id: str, db: AsyncSession) -> uuid.UUID:
    result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user.organization_id


@router.get("/{telegram_user_id}", response_model=list[SisterFormatOut], dependencies=[Depends(verify_bot_token)])
async def list_sister_formats(telegram_user_id: str, db: AsyncSession = Depends(get_db)):
    """Return all saved sister-quotation format templates for the user's org."""
    org_id = await _get_org_id(telegram_user_id, db)
    result = await db.execute(
        select(SisterFormat)
        .where(SisterFormat.organization_id == org_id)
        .order_by(SisterFormat.created_at)
    )
    return result.scalars().all()


@router.post("/{telegram_user_id}", response_model=SisterFormatOut, dependencies=[Depends(verify_bot_token)])
async def upload_sister_format(
    telegram_user_id: str,
    name: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a new sister-quotation format template. Max 10 per org."""
    org_id = await _get_org_id(telegram_user_id, db)

    count_result = await db.execute(
        select(func.count()).select_from(SisterFormat).where(SisterFormat.organization_id == org_id)
    )
    count = count_result.scalar_one()
    if count >= _MAX_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_FORMATS} sister formats allowed. Delete one to add more.",
        )

    filename = file.filename or "format.pdf"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".pdf"
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only PDF, DOC, and DOCX files are accepted.")

    data = await file.read()
    fmt_id = uuid.uuid4()
    key = f"sister-formats/{org_id}/{fmt_id}{suffix}"
    upload_file(settings.minio_bucket_assets, key, data)

    record = SisterFormat(
        id=fmt_id,
        organization_id=org_id,
        name=name.strip(),
        file_key=key,
        original_filename=filename,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/{telegram_user_id}/{format_id}", dependencies=[Depends(verify_bot_token)])
async def delete_sister_format(
    telegram_user_id: str,
    format_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a sister-quotation format template."""
    org_id = await _get_org_id(telegram_user_id, db)
    result = await db.execute(
        select(SisterFormat).where(
            SisterFormat.id == format_id,
            SisterFormat.organization_id == org_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Format not found.")

    try:
        delete_file(settings.minio_bucket_assets, record.file_key)
    except Exception:
        pass

    await db.delete(record)
    await db.commit()
    return {"deleted": str(format_id)}


@router.get("/{telegram_user_id}/{format_id}/download", dependencies=[Depends(verify_bot_token)])
async def get_format_file_key(
    telegram_user_id: str,
    format_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the MinIO file_key for a format so the bot can download it directly."""
    org_id = await _get_org_id(telegram_user_id, db)
    result = await db.execute(
        select(SisterFormat).where(
            SisterFormat.id == format_id,
            SisterFormat.organization_id == org_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Format not found.")
    return {"file_key": record.file_key, "original_filename": record.original_filename}
