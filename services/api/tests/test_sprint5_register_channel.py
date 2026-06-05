#genai: Sprint 5 — register-channel route shape + schema.
from __future__ import annotations

import inspect


def test_register_channel_route_present():
    from app.routes.auth import router

    paths = {r.path for r in router.routes}
    assert "/api/v1/auth/register-channel" in paths


def test_register_channel_request_schema_has_channel_and_handle():
    from app.schemas.schemas import ChannelRegisterRequest

    fields = set(ChannelRegisterRequest.model_fields.keys())
    assert "channel" in fields
    assert "handle" in fields
    assert "name" in fields
    assert "company_name" in fields


def test_register_channel_handler_uses_bot_token_dep():
    """Only an authenticated bot adapter can call register-channel."""
    from app.routes.auth import router

    target = None
    for r in router.routes:
        if r.path == "/api/v1/auth/register-channel":
            target = r
            break
    assert target is not None
    # FastAPI's `APIRoute` exposes the dependencies via the `dependant` tree;
    # the `verify_bot_token` callable lives on each child dependant's `call`.
    calls = [str(d.call) for d in target.dependant.dependencies]
    assert any("verify_bot_token" in c for c in calls), (
        f"register-channel must be gated on verify_bot_token; got {calls}"
    )


def test_register_channel_source_handles_all_channels():
    import app.routes.auth as auth_mod

    src = inspect.getsource(auth_mod.register_channel)
    # Whitelist enforcement
    assert "_VALID_CHANNELS" in src
    # Telegram backward-compat: the legacy `users.telegram_user_id` column
    # still has to be populated for `telegram` callers.
    assert 'channel == "telegram"' in src
