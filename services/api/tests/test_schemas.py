"""
#genai: Phase 2 — sanity tests for the new schemas + migration script.

We don't spin up a Postgres in CI, so we verify shape & defaults at the Pydantic
level and confirm the alembic migration module imports cleanly with the right
revision metadata. Full DB-level testing happens at deploy time via `alembic upgrade head`.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_company_profile_out_includes_new_counters():
    from app.schemas.schemas import CompanyProfileOut
    fields = CompanyProfileOut.model_fields
    assert "po_prefix" in fields
    assert "po_counter" in fields
    assert "quotation_prefix" in fields
    assert "quotation_counter" in fields


def test_company_profile_update_accepts_new_prefixes():
    from app.schemas.schemas import CompanyProfileUpdate
    obj = CompanyProfileUpdate(po_prefix="PO", quotation_prefix="QT", invoice_prefix="INV")
    assert obj.po_prefix == "PO"
    assert obj.quotation_prefix == "QT"
    assert obj.invoice_prefix == "INV"


def test_document_log_request_supports_chaining_fields():
    from app.schemas.schemas import DocumentLogRequest
    req = DocumentLogRequest(
        feature="create_invoice",
        original_filename="(scratch)",
        output_filename="INV-0001.pdf",
        output_file_key="outputs/x.pdf",
        input_file_key="inputs/x.pdf",
        source_document_id="11111111-2222-3333-4444-555555555555",
        document_type="invoice",
    )
    assert req.input_file_key == "inputs/x.pdf"
    assert req.document_type == "invoice"


def test_increment_counter_schemas():
    from app.schemas.schemas import IncrementCounterRequest, IncrementCounterResponse
    req = IncrementCounterRequest(counter_type="invoice")
    assert req.counter_type == "invoice"
    resp = IncrementCounterResponse(counter_type="invoice", new_value=5)
    assert resp.new_value == 5


def test_document_metadata_out_defaults():
    from app.schemas.schemas import DocumentMetadataOut
    import uuid as _uuid
    from datetime import datetime, timezone
    m = DocumentMetadataOut(
        id=_uuid.uuid4(),
        feature="create_invoice",
        document_type="invoice",
        output_filename="x.pdf",
        output_file_key="o/x.pdf",
        created_at=datetime.now(tz=timezone.utc),
    )
    assert m.parsed_data == {}
    assert m.document_type == "invoice"


def test_migration_003_has_correct_metadata():
    """
    The local `services/api/alembic/` directory shadows the installed `alembic`
    package at import-time, so we verify the migration script via source-level
    parsing instead of exec'ing it. The actual upgrade/downgrade is exercised
    by `alembic upgrade head` at deploy time.
    """
    mig_path = ROOT / "alembic" / "versions" / "003_v2_features.py"
    assert mig_path.exists(), f"Missing migration: {mig_path}"
    src = mig_path.read_text()
    assert 'revision = "003"' in src
    assert 'down_revision = "002"' in src
    assert "def upgrade()" in src
    assert "def downgrade()" in src
    # Confirm the three new column families are added
    assert "po_prefix" in src and "po_counter" in src
    assert "quotation_prefix" in src and "quotation_counter" in src
    assert "input_file_key" in src
    assert "source_document_id" in src
    assert "document_type" in src


def test_orm_model_has_new_columns():
    from app.models.models import CompanyProfile, Document
    cp_cols = {c.name for c in CompanyProfile.__table__.columns}
    assert "po_prefix" in cp_cols
    assert "po_counter" in cp_cols
    assert "quotation_prefix" in cp_cols
    assert "quotation_counter" in cp_cols

    doc_cols = {c.name for c in Document.__table__.columns}
    assert "input_file_key" in doc_cols
    assert "source_document_id" in doc_cols
    assert "document_type" in doc_cols
