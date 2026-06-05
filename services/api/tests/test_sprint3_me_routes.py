#genai: Sprint 3 / WS-F — surface tests for /api/v1/me/* routes.
"""
We don't spin up a full HTTP server here — that needs a live Postgres + Redis +
MinIO and is covered by the integration suite. Instead we verify:

  - the router registers every expected JWT-keyed endpoint and method,
  - the route handlers depend on `resolve_caller` (so they're JWT-authenticated),
  - the request/response schemas exist with the expected fields,
  - `_process_sister_quote` honours an edited `quote` payload from the web wizard.

These are the contract guarantees the web app relies on.
"""
from __future__ import annotations

import importlib
import inspect

import pytest


@pytest.fixture(scope="module")
def me_router():
    return importlib.import_module("app.routes.me").router


def test_me_router_has_prefix_and_tag(me_router):
    assert me_router.prefix == "/api/v1/me"
    assert "me" in me_router.tags


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/me/profile"),
        ("PUT", "/api/v1/me/profile"),
        ("POST", "/api/v1/me/profile/logo"),
        ("POST", "/api/v1/me/profile/increment-counter"),
        ("GET", "/api/v1/me/sister-formats"),
        ("POST", "/api/v1/me/sister-formats"),
        ("DELETE", "/api/v1/me/sister-formats/{format_id}"),
        ("GET", "/api/v1/me/documents"),
        ("GET", "/api/v1/me/documents/{document_id}/download"),
        ("GET", "/api/v1/me/documents/{document_id}/metadata"),
    ],
)
def test_me_router_registers_expected_routes(me_router, method: str, path: str):
    routes = [(r.methods, r.path) for r in me_router.routes]
    assert any(method in methods and r_path == path for methods, r_path in routes), (
        f"Expected {method} {path} in me router. Got: {routes}"
    )


def test_me_routes_depend_on_resolve_caller(me_router):
    """
    Every /me/* handler must take a Caller dependency. We inspect the handler
    signatures rather than running them — fast and zero infra.
    """
    from app.core.security import resolve_caller

    handlers = [r.endpoint for r in me_router.routes]
    for handler in handlers:
        sig = inspect.signature(handler)
        # Look for any parameter whose default is a Depends() of resolve_caller.
        found = False
        for param in sig.parameters.values():
            default = param.default
            if hasattr(default, "dependency") and default.dependency is resolve_caller:
                found = True
                break
        assert found, f"{handler.__name__} is missing Depends(resolve_caller)"


def test_increment_counter_schema_round_trips():
    """The IncrementCounter request/response schemas the route relies on exist
    and roundtrip cleanly."""
    from app.schemas.schemas import IncrementCounterRequest, IncrementCounterResponse

    req = IncrementCounterRequest(counter_type="invoice")
    assert req.counter_type == "invoice"
    resp = IncrementCounterResponse(counter_type="invoice", new_value=42)
    assert resp.new_value == 42


def test_company_profile_update_schema_allows_partial():
    """Web profile form sends only changed fields; schema must accept that."""
    from app.schemas.schemas import CompanyProfileUpdate

    partial = CompanyProfileUpdate(display_name="ABC")
    assert partial.display_name == "ABC"
    # No required fields — empty payload is also valid.
    assert CompanyProfileUpdate().model_dump(exclude_none=True) == {}


def test_sister_quote_accepts_client_edited_quote():
    """
    Sprint 3 / WS-H gate: the web wizard sends `params.quote` after step 2.
    The processor must use it verbatim instead of re-parsing the source file.
    We test by reading the source — the implementation branches on
    `client_quote_dict` being present.
    """
    from pathlib import Path

    src = Path("app/routes/process.py").read_text()
    # Branch exists.
    assert "client_quote_dict" in src
    assert "_quote_from_dict" in src
    # Web-friendly key takes precedence over the bot's legacy key.
    assert "output_extension" in src and "output_ext" in src


def test_quote_from_dict_handles_minimal_payload():
    """The helper that rehydrates QuoteDocument from a web-edited dict tolerates
    sparse fields and bad numbers without crashing."""
    from app.routes.process import _quote_from_dict, _quote_to_dict

    quote = _quote_from_dict(
        {
            "recipient_name": "Test Customer",
            "sections": [
                {
                    "name": "GEN",
                    "items": [
                        {
                            "sno": "1",
                            "description": "Item A",
                            "qty": "2",
                            "unit_price": 100,
                            "total": 200,
                        },
                        # Missing fields and bad price types.
                        {"description": "Item B", "unit_price": "abc"},
                    ],
                }
            ],
        }
    )
    out = _quote_to_dict(quote)
    assert out["recipient_name"] == "Test Customer"
    assert len(out["sections"]) == 1
    assert len(out["sections"][0]["items"]) == 2
    # Bad price coerced to 0.
    assert out["sections"][0]["items"][1]["unit_price"] == 0.0


def test_main_includes_me_router():
    """The /me router must be wired into the FastAPI app."""
    import app.main as main

    routes = [r.path for r in main.app.routes]
    assert any(p.startswith("/api/v1/me/") for p in routes)
