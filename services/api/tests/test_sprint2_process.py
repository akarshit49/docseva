"""
#genai: Sprint 2 — verify the /process router shape and auth wiring.

We don't run the full processor pipeline here (that needs OpenAI + MinIO);
those are covered by services/bot/tests/* which exercise the processors as
library code. These tests confirm the API surface itself.
"""
from __future__ import annotations

import importlib
import inspect


def test_process_router_registers_endpoint():
    from app.routes.process import router

    paths = [route.path for route in router.routes]
    assert any("/process/{feature}" in p for p in paths)


def test_process_supported_features_include_tier1_and_tier2():
    from app.routes.process import _SUPPORTED_FEATURES

    # Tier 1 anchor
    assert "sister_quote" in _SUPPORTED_FEATURES
    # Tier 2 coherent toolkit
    assert "bill_to_make" in _SUPPORTED_FEATURES
    assert "compare" in _SUPPORTED_FEATURES
    assert "gst_validate" in _SUPPORTED_FEATURES


def test_process_implemented_features_in_sprint2():
    """Sprint 2's must-haves are wired; the rest 501 until later sprints."""
    from app.routes.process import _IMPLEMENTED_FEATURES

    must_have = {"sister_quote", "bill_to_make", "compare", "gst_validate"}
    assert must_have.issubset(_IMPLEMENTED_FEATURES)


def test_process_response_schema_shape():
    from app.schemas.schemas import ProcessQuota, ProcessResponse

    resp = ProcessResponse(
        output_filename="x.docx",
        parsed_data={"a": 1},
        needs_confirmation=True,
        quota=ProcessQuota(used=2, limit=10),
    )
    payload = resp.model_dump()
    assert payload["parsed_data"] == {"a": 1}
    assert payload["needs_confirmation"] is True
    assert payload["quota"] == {"used": 2, "limit": 10}


def test_caller_dataclass_carries_channel():
    from app.core.security import Caller
    import uuid

    c = Caller(
        user_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        channel="telegram",
    )
    assert c.channel == "telegram"


def test_resolve_caller_signature_has_dual_auth_headers():
    """The resolver accepts either bearer JWT or X-Bot-Token + X-User-Id."""
    from app.core.security import resolve_caller

    sig = inspect.signature(resolve_caller)
    params = set(sig.parameters)
    assert "authorization" in params
    assert "x_bot_token" in params
    assert "x_user_id" in params
    assert "x_channel" in params


def test_processors_module_accessible_from_api():
    """Sprint 2 moved processors into the API package."""
    mod = importlib.import_module("app.processors.service")
    assert hasattr(mod, "convert_with_template")
    assert hasattr(mod, "convert_with_data")
    assert hasattr(mod, "adjust_prices")

    bill = importlib.import_module("app.processors.bill_to_make")
    assert hasattr(bill, "generate_bill")

    gst = importlib.import_module("app.processors.gst_validator")
    assert hasattr(gst, "validate_invoice")

    cmp_mod = importlib.import_module("app.processors.quotation_compare")
    assert hasattr(cmp_mod, "compare_quotations")


def test_bot_api_client_exposes_process_helper():
    """Cross-service spot check: the bot's api_client gained the process() helper."""
    from pathlib import Path
    import re

    src_path = (
        Path(__file__).resolve().parents[2] / "bot" / "app" / "api_client.py"
    )
    src = src_path.read_text()
    # `process(` definition must accept the expected kwargs.
    assert "def process(" in src
    for kw in ("telegram_user_id", "feature", "format_id", "mode"):
        assert kw in src, f"api_client.process missing kwarg: {kw}"
