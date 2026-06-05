#genai: Sprint 2 / WS-C — generic /api/v1/process/<feature> endpoint.
"""
Single, channel-agnostic surface for every document feature:

    POST /api/v1/process/{feature}

Authenticated by either:
  - Authorization: Bearer <JWT>  (web)
  - X-Bot-Token + X-User-Id + X-Channel  (telegram / whatsapp)

Multipart fields:
  - file               required for upload-based features
  - files              for multi-upload features (compare)
  - params (JSON str)  feature-specific extras (HSN map, BillTo, prices etc.)
  - format_id          UUID of a saved SisterFormat (sister_quote only)
  - mode               'preview' | 'final'  (sister_quote / bill_to_make only)

Returns `ProcessResponse` — see schemas.py. In `mode=preview` we extract +
parse but skip rendering/quota; in `mode=final` we render, persist outputs,
write a Document row, and increment the quota.
"""
from __future__ import annotations

import json
import logging
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path as FastapiPath,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.error_messages import raise_api_error
from app.core.security import Caller, resolve_caller
from app.core.storage import presigned_url, upload_file, upload_local_file
from app.models.models import (
    CompanyProfile,
    Document,
    Organization,
    SisterFormat,
)
from app.schemas.schemas import ProcessQuota, ProcessResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/process", tags=["process"])

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
_SUPPORTED_FEATURES = {
    "sister_quote",
    "bill_to_make",
    "compare",
    "gst_validate",
    "to_docx",
    "to_pdf",
    "watermark",
    "bg_remove",
    "catalog",
    "rename",
    "create_quote",
    "create_invoice",
    "create_po",
}
_IMPLEMENTED_FEATURES = {
    "sister_quote",
    "bill_to_make",
    "compare",
    "gst_validate",
    "watermark",
    "bg_remove",
    "catalog",
}

#genai: Image extensions accepted by the image-based tools (watermark, bg-remove, catalog).
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif", ".bmp"}


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _load_company_profile(db: AsyncSession, org_id: uuid.UUID) -> dict:
    q = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == org_id)
    )
    profile = q.scalar_one_or_none()
    return profile.as_dict() if profile else {}


async def _enforce_quota(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    q = await db.execute(select(Organization).where(Organization.id == org_id))
    org = q.scalar_one()
    if org.docs_used_this_cycle >= org.docs_limit_per_cycle:
        raise_api_error(
            "E004",
            details={
                "used": org.docs_used_this_cycle,
                "limit": org.docs_limit_per_cycle,
            },
        )
    return org


async def _increment_quota(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    q = await db.execute(select(Organization).where(Organization.id == org_id))
    org = q.scalar_one()
    org.docs_used_this_cycle += 1
    await db.commit()
    await db.refresh(org)
    return org


def _parse_params(params_json: str | None) -> dict:
    if not params_json:
        return {}
    try:
        out = json.loads(params_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="`params` must be valid JSON.")
    if not isinstance(out, dict):
        raise HTTPException(status_code=400, detail="`params` must be a JSON object.")
    return out


async def _save_upload(file: UploadFile, tmp_dir: Path) -> Path:
    """Save an UploadFile to `tmp_dir`. Enforce size + non-empty + safe filename."""
    if not file.filename:
        raise_api_error("E007")
    data = await file.read()
    if not data:
        raise_api_error("E003")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise_api_error("E006", details={"size_mb": round(len(data) / 1_048_576, 1)})
    # Sanitise filename to a single path component.
    safe = Path(file.filename).name
    dest = tmp_dir / safe
    dest.write_bytes(data)
    return dest


async def _persist_document(
    db: AsyncSession,
    *,
    caller: Caller,
    feature: str,
    document_type: str | None,
    original_filename: str | None,
    output_filename: str | None,
    output_file_key: str | None,
    input_file_key: str | None,
    parsed_data: dict,
) -> Document:
    expires_at = datetime.now(tz=timezone.utc) + timedelta(
        days=settings.document_retention_days
    )
    doc = Document(
        organization_id=caller.organization_id,
        user_id=caller.user_id,
        feature=feature,
        status="completed",
        original_filename=original_filename,
        output_filename=output_filename,
        output_file_key=output_file_key,
        input_file_key=input_file_key,
        document_type=document_type,
        doc_metadata=parsed_data or {},
        expires_at=expires_at,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


def _quote_to_dict(quote) -> dict:
    """Convert a QuoteDocument dataclass to a plain JSON-serialisable dict."""
    sections = []
    for sec in quote.sections:
        sections.append(
            {
                "name": sec.name,
                "items": [
                    {
                        "sno": item.sno,
                        "description": item.description,
                        "qty": item.qty,
                        "unit_price": item.unit_price,
                        "total": item.total,
                    }
                    for item in sec.items
                ],
            }
        )
    return {
        "recipient_name": quote.recipient_name,
        "recipient_address_lines": quote.recipient_address_lines,
        "subject": quote.subject,
        "ref_no": quote.ref_no,
        "date": quote.date,
        "valid_until": quote.valid_until,
        "sections": sections,
        "subtotal": quote.subtotal,
    }


def _quote_from_dict(data: dict):
    """
    Reverse of `_quote_to_dict`: rehydrate a `QuoteDocument` from a JSON-ish
    dict shape (the web wizard's edited preview). Tolerant of missing fields.
    """
    from app.processors.models import QuoteDocument, QuoteItem, QuoteSection

    sections_raw = data.get("sections") or []
    sections: list = []
    for sec in sections_raw:
        items_raw = sec.get("items") or []
        items = []
        for it in items_raw:
            try:
                unit_price = float(it.get("unit_price") or 0)
            except (TypeError, ValueError):
                unit_price = 0.0
            try:
                total = float(it.get("total") or 0)
            except (TypeError, ValueError):
                total = 0.0
            items.append(
                QuoteItem(
                    sno=str(it.get("sno") or ""),
                    description=str(it.get("description") or ""),
                    qty=str(it.get("qty") or "1"),
                    unit_price=unit_price,
                    total=total,
                )
            )
        sections.append(QuoteSection(name=str(sec.get("name") or "GENERAL"), items=items))

    return QuoteDocument(
        recipient_name=str(data.get("recipient_name") or ""),
        recipient_address_lines=list(data.get("recipient_address_lines") or []),
        subject=str(data.get("subject") or ""),
        ref_no=str(data.get("ref_no") or ""),
        date=str(data.get("date") or ""),
        valid_until=str(data.get("valid_until") or ""),
        sections=sections,
    )


# ── Feature implementations ──────────────────────────────────────────────────


async def _process_sister_quote(
    *,
    db: AsyncSession,
    caller: Caller,
    file: UploadFile,
    params: dict,
    format_id: Optional[uuid.UUID],
    mode: str,
) -> ProcessResponse:
    from app.processors.formats import TargetFormat
    from app.processors.service import (
        adjust_prices,
        convert_with_data,
        convert_with_template,
    )
    from app.core.storage import download_file

    if not file:
        raise_api_error("E003")

    with tempfile.TemporaryDirectory(prefix="docseva_proc_") as tmp_str:
        tmp_dir = Path(tmp_str)
        input_path = await _save_upload(file, tmp_dir)

        company_profile = await _load_company_profile(db, caller.organization_id)
        price_adjust_pct = params.get("price_adjust_pct")
        #genai: Sprint 3 / WS-H — web wizard sends `output_extension`; bot sends
        #       `output_ext`. Accept both for compatibility.
        output_ext = (
            params.get("output_extension") or params.get("output_ext") or "docx"
        ).lower()
        if output_ext not in {"docx", "pdf"}:
            output_ext = "docx"
        #genai: Sprint 3 / WS-H — if the web wizard already showed the user a
        #       preview and let them edit items, the edited dict is sent back
        #       here as `params.quote`. Skip re-parsing and use it verbatim.
        client_quote_dict = params.get("quote") if isinstance(params.get("quote"), dict) else None

        # Resolve a format template if the user picked one.
        template_path: Path | None = None
        if format_id:
            fmt_q = await db.execute(
                select(SisterFormat).where(
                    SisterFormat.id == format_id,
                    SisterFormat.organization_id == caller.organization_id,
                )
            )
            fmt = fmt_q.scalar_one_or_none()
            if not fmt:
                raise_api_error("E010")
            try:
                data = download_file(settings.minio_bucket_assets, fmt.file_key)
                template_path = tmp_dir / Path(fmt.original_filename).name
                template_path.write_bytes(data)
            except Exception as exc:
                logger.warning("Failed to download format template: %s", exc)
                raise_api_error("E010")

        output_name = f"{Path(input_path).stem}_branded.{output_ext}"
        output_path = tmp_dir / output_name

        try:
            fmt_value = (params.get("target_format") or "sv_enterprises").lower()
            try:
                target = TargetFormat(fmt_value)
            except ValueError:
                target = TargetFormat.SV_ENTERPRISES

            if client_quote_dict is not None:
                # Web wizard's edited quote → render directly without re-parsing.
                from app.processors.renderers import render as render_quote

                quote = _quote_from_dict(client_quote_dict)
                if price_adjust_pct:
                    try:
                        pct = float(price_adjust_pct)
                    except (TypeError, ValueError):
                        pct = 0.0
                    if pct:
                        quote = adjust_prices(quote, pct)
                render_quote(quote, target, output_path, company_profile)
            elif template_path is not None:
                _, quote = convert_with_template(
                    input_path, template_path, output_path, company_profile
                )
                if price_adjust_pct:
                    try:
                        pct = float(price_adjust_pct)
                    except (TypeError, ValueError):
                        pct = 0.0
                    if pct:
                        quote = adjust_prices(quote, pct)
                        from app.processors.renderers import render as render_quote

                        render_quote(quote, target, output_path, company_profile)
            else:
                _, quote = convert_with_data(
                    input_path, target, output_path, company_profile
                )
                if price_adjust_pct:
                    try:
                        pct = float(price_adjust_pct)
                    except (TypeError, ValueError):
                        pct = 0.0
                    if pct:
                        quote = adjust_prices(quote, pct)
                        from app.processors.renderers import render as render_quote

                        render_quote(quote, target, output_path, company_profile)
        except Exception as exc:
            logger.exception("sister_quote processing failed: %s", exc)
            raise_api_error("E002", details={"reason": str(exc)})

        parsed = _quote_to_dict(quote)

        if mode == "preview":
            return ProcessResponse(
                parsed_data=parsed,
                needs_confirmation=True,
            )

        # mode == "final" — quota check + persist + return links.
        await _enforce_quota(db, caller.organization_id)

        doc_id = uuid.uuid4()
        input_key = f"uploads/{caller.organization_id}/{doc_id}/{input_path.name}"
        output_key = f"outputs/{caller.organization_id}/{doc_id}/{output_name}"
        upload_local_file(settings.minio_bucket_uploads, input_key, input_path)
        upload_local_file(settings.minio_bucket_outputs, output_key, output_path)

        # Reuse the pre-generated UUID so MinIO keys and the Document row align.
        expires_at = datetime.now(tz=timezone.utc) + timedelta(
            days=settings.document_retention_days
        )
        doc = Document(
            id=doc_id,
            organization_id=caller.organization_id,
            user_id=caller.user_id,
            feature="sister_quote",
            document_type="sister_quote",
            status="completed",
            original_filename=input_path.name,
            output_filename=output_name,
            output_file_key=output_key,
            input_file_key=input_key,
            doc_metadata=parsed,
            expires_at=expires_at,
        )
        db.add(doc)
        await db.commit()

        org = await _increment_quota(db, caller.organization_id)
        return ProcessResponse(
            document_id=doc.id,
            output_filename=output_name,
            output_url=presigned_url(settings.minio_bucket_outputs, output_key),
            input_url=presigned_url(settings.minio_bucket_uploads, input_key),
            parsed_data=parsed,
            needs_confirmation=False,
            quota=ProcessQuota(
                used=org.docs_used_this_cycle,
                limit=org.docs_limit_per_cycle,
            ),
        )


async def _process_bill_to_make(
    *,
    db: AsyncSession,
    caller: Caller,
    file: UploadFile,
    params: dict,
    mode: str,
) -> ProcessResponse:
    from app.processors.bill_to_make import generate_bill

    if not file:
        raise_api_error("E003")

    bill_number = (params.get("bill_number") or "").strip()
    bill_date = (params.get("bill_date") or "").strip()

    # Auto-fill bill_date with today's date if not provided.
    if not bill_date:
        bill_date = datetime.now(tz=timezone.utc).strftime("%d/%m/%Y")

    # Auto-generate bill_number from the organisation's invoice counter when the
    # caller doesn't supply one explicitly (most common path from the web UI).
    _auto_increment_profile: CompanyProfile | None = None
    if not bill_number:
        pq = await db.execute(
            select(CompanyProfile).where(
                CompanyProfile.organization_id == caller.organization_id
            )
        )
        _auto_increment_profile = pq.scalar_one_or_none()
        prefix = (
            _auto_increment_profile.invoice_prefix if _auto_increment_profile else None
        ) or "INV"
        counter = (
            _auto_increment_profile.invoice_counter if _auto_increment_profile else 0
        ) or 0
        bill_number = f"{prefix}-{str(counter + 1).zfill(4)}"

    with tempfile.TemporaryDirectory(prefix="docseva_proc_") as tmp_str:
        tmp_dir = Path(tmp_str)
        input_path = await _save_upload(file, tmp_dir)

        company_profile = await _load_company_profile(db, caller.organization_id)
        output_name = f"{Path(input_path).stem}_invoice.pdf"
        output_path = tmp_dir / output_name

        if mode == "final":
            await _enforce_quota(db, caller.organization_id)
        try:
            generate_bill(
                input_path=input_path,
                output_path=output_path,
                bill_number=bill_number,
                bill_date=bill_date,
                company_profile=company_profile,
            )
        except Exception as exc:
            logger.exception("bill_to_make processing failed: %s", exc)
            raise_api_error("E002", details={"reason": str(exc)})

        # Increment the invoice counter on success so the next call gets the
        # next sequential number.  Only do this for mode=final to avoid burning
        # numbers on previews.
        if mode == "final" and _auto_increment_profile is not None:
            _auto_increment_profile.invoice_counter = (
                _auto_increment_profile.invoice_counter or 0
            ) + 1
            await db.commit()

        if mode == "preview":
            return ProcessResponse(
                needs_confirmation=False,
                parsed_data={"bill_number": bill_number, "bill_date": bill_date},
            )

        doc_id = uuid.uuid4()
        input_key = f"uploads/{caller.organization_id}/{doc_id}/{input_path.name}"
        output_key = f"outputs/{caller.organization_id}/{doc_id}/{output_name}"
        upload_local_file(settings.minio_bucket_uploads, input_key, input_path)
        upload_local_file(settings.minio_bucket_outputs, output_key, output_path)

        doc = await _persist_document(
            db,
            caller=caller,
            feature="bill_to_make",
            document_type="invoice",
            original_filename=input_path.name,
            output_filename=output_name,
            output_file_key=output_key,
            input_file_key=input_key,
            parsed_data={"bill_number": bill_number, "bill_date": bill_date},
        )
        org = await _increment_quota(db, caller.organization_id)
        return ProcessResponse(
            document_id=doc.id,
            output_filename=output_name,
            output_url=presigned_url(settings.minio_bucket_outputs, output_key),
            input_url=presigned_url(settings.minio_bucket_uploads, input_key),
            parsed_data={"bill_number": bill_number, "bill_date": bill_date},
            quota=ProcessQuota(
                used=org.docs_used_this_cycle, limit=org.docs_limit_per_cycle
            ),
        )


async def _process_compare(
    *,
    db: AsyncSession,
    caller: Caller,
    files: list[UploadFile],
    params: dict,
) -> ProcessResponse:
    from app.processors.quotation_compare import compare_quotations

    if not files or len(files) < 2:
        raise HTTPException(
            status_code=400, detail="Provide at least 2 quotation files to compare."
        )
    if len(files) > 10:
        raise HTTPException(
            status_code=400, detail="Maximum 10 quotations may be compared at once."
        )

    with tempfile.TemporaryDirectory(prefix="docseva_proc_") as tmp_str:
        tmp_dir = Path(tmp_str)
        saved: list[tuple[Path, str]] = []
        for f in files:
            path = await _save_upload(f, tmp_dir)
            saved.append((path, f.filename or path.name))

        company_profile = await _load_company_profile(db, caller.organization_id)
        output_name = "quotation_comparison.docx"
        output_path = tmp_dir / output_name

        await _enforce_quota(db, caller.organization_id)
        try:
            compare_quotations(
                files=saved,
                output_path=output_path,
                company_profile=company_profile,
            )
        except Exception as exc:
            logger.exception("compare processing failed: %s", exc)
            raise_api_error("E002", details={"reason": str(exc)})

        doc_id = uuid.uuid4()
        output_key = f"outputs/{caller.organization_id}/{doc_id}/{output_name}"
        upload_local_file(settings.minio_bucket_outputs, output_key, output_path)

        doc = await _persist_document(
            db,
            caller=caller,
            feature="compare",
            document_type="comparison",
            original_filename=", ".join(f.filename or "" for f in files),
            output_filename=output_name,
            output_file_key=output_key,
            input_file_key=None,
            parsed_data={"file_count": len(files)},
        )
        org = await _increment_quota(db, caller.organization_id)
        return ProcessResponse(
            document_id=doc.id,
            output_filename=output_name,
            output_url=presigned_url(settings.minio_bucket_outputs, output_key),
            quota=ProcessQuota(
                used=org.docs_used_this_cycle, limit=org.docs_limit_per_cycle
            ),
        )


async def _process_gst_validate(
    *,
    db: AsyncSession,
    caller: Caller,
    file: UploadFile,
) -> ProcessResponse:
    from app.processors.extractors import extract_text
    from app.processors.gst_validator import validate_invoice

    if not file:
        raise_api_error("E003")

    with tempfile.TemporaryDirectory(prefix="docseva_proc_") as tmp_str:
        tmp_dir = Path(tmp_str)
        input_path = await _save_upload(file, tmp_dir)

        try:
            text = extract_text(input_path)
        except Exception as exc:
            logger.warning("GST extract failed: %s", exc)
            raise_api_error("E001")

        await _enforce_quota(db, caller.organization_id)
        try:
            report = validate_invoice(text)
        except Exception as exc:
            logger.exception("gst_validate failed: %s", exc)
            raise_api_error("E002", details={"reason": str(exc)})

        # Persist report as a text/plain blob so the user can re-download.
        doc_id = uuid.uuid4()
        output_name = f"{Path(input_path).stem}_gst_report.txt"
        output_key = f"outputs/{caller.organization_id}/{doc_id}/{output_name}"
        upload_file(
            settings.minio_bucket_outputs,
            output_key,
            report.encode("utf-8"),
            content_type="text/plain; charset=utf-8",
        )
        input_key = f"uploads/{caller.organization_id}/{doc_id}/{input_path.name}"
        upload_local_file(settings.minio_bucket_uploads, input_key, input_path)

        doc = await _persist_document(
            db,
            caller=caller,
            feature="gst_validate",
            document_type="gst_report",
            original_filename=input_path.name,
            output_filename=output_name,
            output_file_key=output_key,
            input_file_key=input_key,
            parsed_data={"report_preview": report[:400]},
        )
        org = await _increment_quota(db, caller.organization_id)
        return ProcessResponse(
            document_id=doc.id,
            output_filename=output_name,
            output_url=presigned_url(settings.minio_bucket_outputs, output_key),
            input_url=presigned_url(settings.minio_bucket_uploads, input_key),
            parsed_data={"report": report},
            quota=ProcessQuota(
                used=org.docs_used_this_cycle, limit=org.docs_limit_per_cycle
            ),
        )


# ── Image tools (watermark / bg-remove / catalog) ────────────────────────────


async def _download_user_logo(
    db: AsyncSession, *, organization_id: uuid.UUID, tmp_dir: Path
) -> Path | None:
    """Pull the company logo from MinIO to a temp file. Returns None if no logo."""
    from app.core.storage import download_file

    profile_q = await db.execute(
        select(CompanyProfile).where(CompanyProfile.organization_id == organization_id)
    )
    profile = profile_q.scalar_one_or_none()
    if not profile or not profile.logo_key:
        return None
    try:
        data = download_file(settings.minio_bucket_assets, profile.logo_key)
        ext = Path(profile.logo_key).suffix or ".png"
        out = tmp_dir / f"logo{ext}"
        out.write_bytes(data)
        return out
    except Exception as exc:
        logger.warning("Could not fetch company logo: %s", exc)
        return None


def _validate_image_upload(file: UploadFile) -> None:
    name = (file.filename or "").lower()
    ext = Path(name).suffix
    if ext not in _IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type '{ext}'. Use PNG, JPG, JPEG, WEBP, HEIC, or BMP.",
        )


async def _process_watermark(
    *,
    db: AsyncSession,
    caller: Caller,
    file: UploadFile,
    params: dict,
) -> ProcessResponse:
    from app.processors.watermark import add_watermark

    if not file:
        raise_api_error("E003")
    _validate_image_upload(file)

    mode = (params.get("mode") or "logo").lower().strip()
    if mode not in {"logo", "text"}:
        mode = "logo"
    text = (params.get("text") or "").strip() or None
    try:
        opacity = float(params.get("opacity") or 0.30)
    except (TypeError, ValueError):
        opacity = 0.30
    opacity = max(0.05, min(1.0, opacity))
    try:
        size_fraction = float(params.get("size_fraction") or 0.38)
    except (TypeError, ValueError):
        size_fraction = 0.38
    size_fraction = max(0.10, min(0.90, size_fraction))

    if mode == "text" and not text:
        raise HTTPException(
            status_code=400,
            detail="Text watermark requires a non-empty `text` value in params.",
        )

    with tempfile.TemporaryDirectory(prefix="docseva_wm_") as tmp_str:
        tmp_dir = Path(tmp_str)
        input_path = await _save_upload(file, tmp_dir)

        logo_path: Path | None = None
        if mode == "logo":
            logo_path = await _download_user_logo(
                db, organization_id=caller.organization_id, tmp_dir=tmp_dir
            )

        output_name = f"{Path(input_path).stem}_watermarked.png"
        output_path = tmp_dir / output_name

        await _enforce_quota(db, caller.organization_id)
        try:
            add_watermark(
                image_path=input_path,
                output_path=output_path,
                mode=mode,
                text=text,
                opacity=opacity,
                size_fraction=size_fraction,
                logo_path=logo_path,
            )
        except Exception as exc:
            logger.exception("watermark processing failed: %s", exc)
            raise_api_error("E002", details={"reason": str(exc)})

        doc_id = uuid.uuid4()
        input_key = f"uploads/{caller.organization_id}/{doc_id}/{input_path.name}"
        output_key = f"outputs/{caller.organization_id}/{doc_id}/{output_name}"
        upload_local_file(settings.minio_bucket_uploads, input_key, input_path)
        upload_local_file(settings.minio_bucket_outputs, output_key, output_path)

        doc = await _persist_document(
            db,
            caller=caller,
            feature="watermark",
            document_type="image",
            original_filename=input_path.name,
            output_filename=output_name,
            output_file_key=output_key,
            input_file_key=input_key,
            parsed_data={
                "mode": mode,
                "opacity": opacity,
                "size_fraction": size_fraction,
                "has_logo": logo_path is not None,
            },
        )
        org = await _increment_quota(db, caller.organization_id)
        return ProcessResponse(
            document_id=doc.id,
            output_filename=output_name,
            output_url=presigned_url(settings.minio_bucket_outputs, output_key),
            input_url=presigned_url(settings.minio_bucket_uploads, input_key),
            parsed_data={
                "mode": mode,
                "applied_logo": logo_path is not None,
                "opacity": opacity,
            },
            quota=ProcessQuota(
                used=org.docs_used_this_cycle, limit=org.docs_limit_per_cycle
            ),
        )


async def _process_bg_remove(
    *, db: AsyncSession, caller: Caller, file: UploadFile
) -> ProcessResponse:
    from app.processors.bg_remove import remove_background

    if not file:
        raise_api_error("E003")
    _validate_image_upload(file)

    with tempfile.TemporaryDirectory(prefix="docseva_bg_") as tmp_str:
        tmp_dir = Path(tmp_str)
        input_path = await _save_upload(file, tmp_dir)

        output_name = f"{Path(input_path).stem}_nobg.png"
        output_path = tmp_dir / output_name

        await _enforce_quota(db, caller.organization_id)
        try:
            remove_background(image_path=input_path, output_path=output_path)
        except RuntimeError as exc:
            # rembg not installed in this image — return a friendly 503 so the UI
            # can surface a clear message instead of a 500 stack trace.
            logger.error("bg_remove dependency missing: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=(
                    "Background removal is temporarily unavailable on this server "
                    "(missing AI model dependency). Please contact support."
                ),
            )
        except Exception as exc:
            logger.exception("bg_remove processing failed: %s", exc)
            raise_api_error("E002", details={"reason": str(exc)})

        doc_id = uuid.uuid4()
        input_key = f"uploads/{caller.organization_id}/{doc_id}/{input_path.name}"
        output_key = f"outputs/{caller.organization_id}/{doc_id}/{output_name}"
        upload_local_file(settings.minio_bucket_uploads, input_key, input_path)
        upload_local_file(settings.minio_bucket_outputs, output_key, output_path)

        doc = await _persist_document(
            db,
            caller=caller,
            feature="bg_remove",
            document_type="image",
            original_filename=input_path.name,
            output_filename=output_name,
            output_file_key=output_key,
            input_file_key=input_key,
            parsed_data={},
        )
        org = await _increment_quota(db, caller.organization_id)
        return ProcessResponse(
            document_id=doc.id,
            output_filename=output_name,
            output_url=presigned_url(settings.minio_bucket_outputs, output_key),
            input_url=presigned_url(settings.minio_bucket_uploads, input_key),
            quota=ProcessQuota(
                used=org.docs_used_this_cycle, limit=org.docs_limit_per_cycle
            ),
        )


async def _process_catalog(
    *,
    db: AsyncSession,
    caller: Caller,
    file: UploadFile,
    params: dict,
) -> ProcessResponse:
    from app.processors.catalog_pdf import generate_catalog

    if not file:
        raise_api_error("E003")
    _validate_image_upload(file)

    item_name = (params.get("item_name") or "").strip()
    if not item_name:
        raise HTTPException(
            status_code=400,
            detail="`item_name` is required in params (the product title).",
        )
    price = (params.get("price") or "").strip() or None
    description = (params.get("description") or "").strip() or None

    with tempfile.TemporaryDirectory(prefix="docseva_cat_") as tmp_str:
        tmp_dir = Path(tmp_str)
        input_path = await _save_upload(file, tmp_dir)

        company_profile = await _load_company_profile(db, caller.organization_id)
        logo_path = await _download_user_logo(
            db, organization_id=caller.organization_id, tmp_dir=tmp_dir
        )

        # Build a safe filename from the item name.
        safe_stem = "".join(c if c.isalnum() or c in "-_ " else "_" for c in item_name).strip()
        if not safe_stem:
            safe_stem = "catalog"
        output_name = f"{safe_stem[:60]}_catalog.pdf"
        output_path = tmp_dir / output_name

        await _enforce_quota(db, caller.organization_id)
        try:
            generate_catalog(
                image_path=input_path,
                output_path=output_path,
                item_name=item_name,
                price=price,
                description=description,
                company_profile=company_profile,
                logo_path=logo_path,
            )
        except Exception as exc:
            logger.exception("catalog processing failed: %s", exc)
            raise_api_error("E002", details={"reason": str(exc)})

        doc_id = uuid.uuid4()
        input_key = f"uploads/{caller.organization_id}/{doc_id}/{input_path.name}"
        output_key = f"outputs/{caller.organization_id}/{doc_id}/{output_name}"
        upload_local_file(settings.minio_bucket_uploads, input_key, input_path)
        upload_local_file(settings.minio_bucket_outputs, output_key, output_path)

        doc = await _persist_document(
            db,
            caller=caller,
            feature="catalog",
            document_type="catalog",
            original_filename=input_path.name,
            output_filename=output_name,
            output_file_key=output_key,
            input_file_key=input_key,
            parsed_data={
                "item_name": item_name,
                "price": price,
                "description": description,
            },
        )
        org = await _increment_quota(db, caller.organization_id)
        return ProcessResponse(
            document_id=doc.id,
            output_filename=output_name,
            output_url=presigned_url(settings.minio_bucket_outputs, output_key),
            input_url=presigned_url(settings.minio_bucket_uploads, input_key),
            parsed_data={
                "item_name": item_name,
                "price": price,
                "description": description,
            },
            quota=ProcessQuota(
                used=org.docs_used_this_cycle, limit=org.docs_limit_per_cycle
            ),
        )


# ── Router ───────────────────────────────────────────────────────────────────


@router.post("/{feature}", response_model=ProcessResponse)
async def process_feature(
    feature: str = FastapiPath(..., description="Feature name (e.g. sister_quote)"),
    file: UploadFile | None = File(default=None),
    files: list[UploadFile] | None = File(default=None),
    params: str | None = Form(default=None),
    format_id: uuid.UUID | None = Form(default=None),
    mode: str = Form(default="final"),
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
) -> ProcessResponse:
    feature = feature.lower().strip()
    if feature not in _SUPPORTED_FEATURES:
        raise HTTPException(status_code=404, detail=f"Unknown feature: {feature}")
    if feature not in _IMPLEMENTED_FEATURES:
        raise HTTPException(
            status_code=501,
            detail=(
                f"Feature '{feature}' is on the roadmap but not yet implemented "
                "via the unified /process endpoint. Use the legacy endpoints "
                "for now or check back next sprint."
            ),
        )

    parsed_params = _parse_params(params)
    mode = mode.lower().strip()
    if mode not in {"preview", "final"}:
        mode = "final"

    if feature == "sister_quote":
        if file is None:
            raise_api_error("E003")
        return await _process_sister_quote(
            db=db,
            caller=caller,
            file=file,
            params=parsed_params,
            format_id=format_id,
            mode=mode,
        )
    if feature == "bill_to_make":
        if file is None:
            raise_api_error("E003")
        return await _process_bill_to_make(
            db=db,
            caller=caller,
            file=file,
            params=parsed_params,
            mode=mode,
        )
    if feature == "compare":
        # FastAPI gives us `files` as a list (could be empty); if the client
        # actually used the `file` field repeatedly, that also works.
        merged = list(files or [])
        if file is not None and file not in merged:
            merged.insert(0, file)
        return await _process_compare(
            db=db, caller=caller, files=merged, params=parsed_params
        )
    if feature == "gst_validate":
        if file is None:
            raise_api_error("E003")
        return await _process_gst_validate(db=db, caller=caller, file=file)
    if feature == "watermark":
        if file is None:
            raise_api_error("E003")
        return await _process_watermark(
            db=db, caller=caller, file=file, params=parsed_params
        )
    if feature == "bg_remove":
        if file is None:
            raise_api_error("E003")
        return await _process_bg_remove(db=db, caller=caller, file=file)
    if feature == "catalog":
        if file is None:
            raise_api_error("E003")
        return await _process_catalog(
            db=db, caller=caller, file=file, params=parsed_params
        )

    # Defensive — every branch above returns; reaching here is a bug.
    raise HTTPException(status_code=500, detail="Process router unreachable branch.")
