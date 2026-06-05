#genai: Sprint 3 / WS-F — JWT-authenticated "me" routes for the web app.
"""
Mirror of the existing bot-keyed routes (profile, sister-formats, documents),
but identified by the resolved `Caller` (JWT or bot+handle) instead of a URL
path parameter.

Why a parallel router instead of widening the existing ones? The existing
routes are URL-keyed by `telegram_user_id` and the bot's HTTP client is
already locked to that shape. Backwards-compat is non-negotiable per the
execution plan §16, so we add a new `/api/v1/me/*` surface for the web app
(and any future SDKs) and let the bot keep its endpoints unchanged.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import Caller, resolve_caller
from app.core.storage import (
    delete_file,
    presigned_url,
    upload_file,
)
from app.models.models import (
    CompanyProfile,
    Document,
    SisterFormat,
)
from app.schemas.schemas import (
    CompanyProfileOut,
    CompanyProfileUpdate,
    DocumentMetadataOut,
    DocumentOut,
    IncrementCounterRequest,
    IncrementCounterResponse,
    SisterFormatOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/me", tags=["me"])

_COUNTER_FIELDS = {
    "invoice": "invoice_counter",
    "po": "po_counter",
    "quotation": "quotation_counter",
}

_FORMAT_ALLOWED_SUFFIXES = {".pdf", ".doc", ".docx"}
_MAX_FORMATS = 10


# ── Profile ───────────────────────────────────────────────────────────────────


async def _load_profile(db: AsyncSession, org_id: _uuid.UUID) -> CompanyProfile:
    q = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == org_id)
    )
    profile = q.scalar_one_or_none()
    if not profile:
        # Always exist after registration; defensive-create just in case.
        profile = CompanyProfile(organization_id=org_id)
        db.add(profile)
        await db.flush()
    return profile


def _serialise_profile(profile: CompanyProfile) -> CompanyProfileOut:
    out = CompanyProfileOut.model_validate(profile)
    if profile.logo_key:
        try:
            out.logo_url = presigned_url(
                settings.minio_bucket_assets, profile.logo_key
            )
        except Exception:
            out.logo_url = None
    return out


@router.get("/profile", response_model=CompanyProfileOut)
async def get_my_profile(
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    profile = await _load_profile(db, caller.organization_id)
    return _serialise_profile(profile)


@router.put("/profile", response_model=CompanyProfileOut)
async def update_my_profile(
    data: CompanyProfileUpdate,
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    profile = await _load_profile(db, caller.organization_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return _serialise_profile(profile)


@router.post("/profile/logo", response_model=CompanyProfileOut)
async def upload_my_logo(
    file: UploadFile = File(...),
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in (
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
    ):
        raise HTTPException(
            status_code=400,
            detail="Only PNG / JPG / WEBP logos are accepted.",
        )

    profile = await _load_profile(db, caller.organization_id)
    ext = (
        (file.filename or "").rsplit(".", 1)[-1].lower()
        if "." in (file.filename or "")
        else "png"
    )
    key = f"logos/{caller.organization_id}/logo.{ext}"
    data = await file.read()
    upload_file(settings.minio_bucket_assets, key, data, file.content_type)

    profile.logo_key = key
    profile.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(profile)
    return _serialise_profile(profile)


@router.post("/profile/increment-counter", response_model=IncrementCounterResponse)
async def increment_my_counter(
    req: IncrementCounterRequest,
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    if req.counter_type not in _COUNTER_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid counter_type. Must be one of: {sorted(_COUNTER_FIELDS)}",
        )
    profile = await _load_profile(db, caller.organization_id)
    field = _COUNTER_FIELDS[req.counter_type]
    new_value = (getattr(profile, field) or 0) + 1
    setattr(profile, field, new_value)
    profile.updated_at = datetime.now(tz=timezone.utc)
    await db.commit()
    return IncrementCounterResponse(counter_type=req.counter_type, new_value=new_value)


# ── Sister formats ───────────────────────────────────────────────────────────


@router.get("/sister-formats", response_model=list[SisterFormatOut])
async def list_my_formats(
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(SisterFormat)
        .where(SisterFormat.organization_id == caller.organization_id)
        .order_by(SisterFormat.created_at)
    )
    return q.scalars().all()


@router.post("/sister-formats", response_model=SisterFormatOut)
async def upload_my_format(
    name: str = Query(..., description="Display name for the saved format."),
    file: UploadFile = File(...),
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    count_q = await db.execute(
        select(func.count())
        .select_from(SisterFormat)
        .where(SisterFormat.organization_id == caller.organization_id)
    )
    count = count_q.scalar_one()
    if count >= _MAX_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_FORMATS} formats. Delete one to add more.",
        )

    filename = file.filename or "format.pdf"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".pdf"
    if suffix not in _FORMAT_ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400, detail="Only PDF, DOC, and DOCX files are accepted."
        )

    data = await file.read()
    fmt_id = _uuid.uuid4()
    key = f"sister-formats/{caller.organization_id}/{fmt_id}{suffix}"
    upload_file(settings.minio_bucket_assets, key, data)

    record = SisterFormat(
        id=fmt_id,
        organization_id=caller.organization_id,
        name=name.strip(),
        file_key=key,
        original_filename=filename,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete("/sister-formats/{format_id}", status_code=204)
async def delete_my_format(
    format_id: _uuid.UUID,
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(SisterFormat).where(
            SisterFormat.id == format_id,
            SisterFormat.organization_id == caller.organization_id,
        )
    )
    record = q.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Format not found.")
    try:
        delete_file(settings.minio_bucket_assets, record.file_key)
    except Exception:
        pass
    await db.delete(record)
    await db.commit()
    return None


# ── Documents (history + downloads) ──────────────────────────────────────────


@router.get("/documents", response_model=list[DocumentOut])
async def list_my_documents(
    limit: int = Query(20, ge=1, le=100),
    feature: str | None = Query(None, description="Filter by feature name."),
    document_type: str | None = Query(None, description="Filter by document type."),
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    """Recent documents for the caller's organization, newest first."""
    stmt = (
        select(Document)
        .where(Document.organization_id == caller.organization_id)
        .order_by(desc(Document.created_at))
        .limit(limit)
    )
    if feature:
        stmt = stmt.where(Document.feature == feature)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)

    docs_result = await db.execute(stmt)
    docs = docs_result.scalars().all()

    out_list: list[DocumentOut] = []
    for doc in docs:
        out = DocumentOut.model_validate(doc)
        if doc.output_file_key:
            try:
                out.download_url = presigned_url(
                    settings.minio_bucket_outputs, doc.output_file_key
                )
            except Exception:
                out.download_url = None
        out_list.append(out)
    return out_list


@router.get("/documents/{document_id}/download")
async def download_my_document(
    document_id: _uuid.UUID,
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == caller.organization_id,
        )
    )
    doc = q.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not doc.output_file_key:
        raise HTTPException(status_code=404, detail="No output file for this document.")
    try:
        url = presigned_url(settings.minio_bucket_outputs, doc.output_file_key)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate download URL.")
    return RedirectResponse(url=url, status_code=302)


@router.get(
    "/documents/{document_id}/metadata",
    response_model=DocumentMetadataOut,
)
async def get_my_document_metadata(
    document_id: _uuid.UUID,
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    q = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == caller.organization_id,
        )
    )
    doc = q.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    return DocumentMetadataOut(
        id=doc.id,
        feature=doc.feature,
        document_type=doc.document_type,
        parsed_data=doc.doc_metadata or {},
        output_filename=doc.output_filename,
        output_file_key=doc.output_file_key,
        created_at=doc.created_at,
    )
