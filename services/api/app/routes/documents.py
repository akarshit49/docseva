#genai: Document logging routes — bot calls these to record every processed file.
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_bot_token
from app.core.storage import presigned_url
from app.models.models import Document, Organization, User
from app.schemas.schemas import DocumentLogRequest, DocumentMetadataOut, DocumentOut

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


@router.post("/{telegram_user_id}", response_model=DocumentOut, dependencies=[Depends(verify_bot_token)])
async def log_document(
    telegram_user_id: str,
    req: DocumentLogRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a successfully processed document in the database."""
    result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    expires_at = datetime.now(tz=timezone.utc) + timedelta(days=settings.document_retention_days)

    #genai: WS-6 — validate source_document_id is a real UUID if provided
    source_uuid: _uuid.UUID | None = None
    if req.source_document_id:
        try:
            source_uuid = _uuid.UUID(req.source_document_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid source_document_id format.")

    doc = Document(
        organization_id=user.organization_id,
        user_id=user.id,
        feature=req.feature,
        status=req.status,
        original_filename=req.original_filename,
        output_filename=req.output_filename,
        output_file_key=req.output_file_key,
        input_file_key=req.input_file_key,
        source_document_id=source_uuid,
        document_type=req.document_type,
        doc_metadata=req.metadata,
        error_message=req.error_message,
        expires_at=expires_at,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    out = DocumentOut.model_validate(doc)
    if doc.output_file_key:
        try:
            out.download_url = presigned_url(settings.minio_bucket_outputs, doc.output_file_key)
        except Exception:
            out.download_url = None
    return out


@router.get("/{telegram_user_id}", response_model=list[DocumentOut], dependencies=[Depends(verify_bot_token)])
async def list_documents(
    telegram_user_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Fetch last N documents for a user (for dashboard history)."""
    result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    docs_result = await db.execute(
        select(Document)
        .where(Document.organization_id == user.organization_id)
        .order_by(desc(Document.created_at))
        .limit(limit)
    )
    docs = docs_result.scalars().all()

    out_list = []
    for doc in docs:
        out = DocumentOut.model_validate(doc)
        if doc.output_file_key:
            try:
                out.download_url = presigned_url(settings.minio_bucket_outputs, doc.output_file_key)
            except Exception:
                out.download_url = None
        out_list.append(out)
    return out_list


#genai: WS-1 / 17.1 — direct download redirect to a presigned MinIO URL
@router.get(
    "/{telegram_user_id}/{document_id}/download",
    dependencies=[Depends(verify_bot_token)],
)
async def download_document(
    telegram_user_id: str,
    document_id: _uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Redirect to a presigned MinIO URL for the document's output file."""
    user_result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    doc_result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == user.organization_id,
        )
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    if not doc.output_file_key:
        raise HTTPException(status_code=404, detail="No output file available for this document.")

    try:
        url = presigned_url(settings.minio_bucket_outputs, doc.output_file_key)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate download URL.")
    return RedirectResponse(url=url, status_code=302)


#genai: WS-8 / 17.2 — structured metadata payload for editing flow
@router.get(
    "/{telegram_user_id}/{document_id}/metadata",
    response_model=DocumentMetadataOut,
    dependencies=[Depends(verify_bot_token)],
)
async def get_document_metadata(
    telegram_user_id: str,
    document_id: _uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the persisted parsed_data for a document (used by edit features)."""
    user_result = await db.execute(select(User).where(User.telegram_user_id == telegram_user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    doc_result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == user.organization_id,
        )
    )
    doc = doc_result.scalar_one_or_none()
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
