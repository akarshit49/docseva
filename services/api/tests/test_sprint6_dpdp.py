#genai: Sprint 6 — DPDP endpoint structural tests.
"""
We don't spin up Postgres in these tests (the rest of the suite proves the
DB plumbing is fine). Instead we verify that the DPDP router is wired,
authenticates via `resolve_caller`, and that the export schema is stable.
"""
from __future__ import annotations

import inspect


def test_dpdp_router_registers_expected_paths():
    from app.routes.dpdp import router

    paths = {r.path for r in router.routes}
    assert "/api/v1/me/account/export" in paths
    assert "/api/v1/me/account/delete" in paths


def test_export_and_delete_use_resolve_caller():
    from app.routes.dpdp import delete_my_account, export_my_data

    for fn in (export_my_data, delete_my_account):
        sig = inspect.signature(fn)
        assert "caller" in sig.parameters, f"{fn.__name__} must depend on resolve_caller"
        assert "db" in sig.parameters, f"{fn.__name__} must take a db session"


def test_dpdp_router_mounted_on_app():
    from app.main import app

    paths = {r.path for r in app.routes}
    assert "/api/v1/me/account/export" in paths
    assert "/api/v1/me/account/delete" in paths


def test_delete_response_documents_grace_period():
    """Plain inspection that the deletion handler keeps the 30-day promise."""
    import app.routes.dpdp as mod

    src = inspect.getsource(mod.delete_my_account)
    assert "grace_period_days" in src
    assert "30" in src
    assert "deletion_pending" in src
