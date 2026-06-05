#genai: Sprint 6 / WS-J — cross-channel parity test.
"""
The plan's "one brain, many faces" promise (§14) only holds if all three
channels — web, Telegram, WhatsApp — converge on the *same* code path inside
the API. This test enforces that contract at three structural levels:

  1. The `/api/v1/process/<feature>` route accepts both bot headers and JWT
     and resolves to the same `Caller` shape.
  2. The Telegram bot's api_client and the WhatsApp bot's api_client send
     the same headers (X-Bot-Token + X-User-Id + X-Channel) and hit the
     same `/process` endpoint.
  3. The processors live in *one* module (`app.processors.*`) — neither
     bot owns a private copy that could drift.

We don't run real PDFs through the pipeline here (that needs network +
OpenAI + storage). Those byte-for-byte equivalence tests are covered by
parity-checked unit tests on the processor modules themselves.
"""
from __future__ import annotations

import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


# ── 1. API surface is channel-blind ──────────────────────────────────────────


def test_process_endpoint_uses_caller_not_telegram_id():
    """`/process/<feature>` must depend on `resolve_caller`, not raw TG id."""
    from app.routes.process import process_feature

    sig = inspect.signature(process_feature)
    assert "caller" in sig.parameters, "process route lost its caller dep"
    # A Telegram-specific user id has no business here:
    assert "telegram_user_id" not in sig.parameters


def test_caller_dependency_returns_same_shape_for_all_channels():
    """Caller exposes exactly: user_id, organization_id, channel."""
    from app.core.security import Caller

    fields = {f.name for f in Caller.__dataclass_fields__.values()}
    assert fields == {"user_id", "organization_id", "channel"}


def test_resolve_caller_handles_web_telegram_and_whatsapp():
    """The resolver inspects channel-agnostic headers."""
    from app.core.security import resolve_caller

    sig = inspect.signature(resolve_caller)
    params = set(sig.parameters)
    # Two auth families:
    assert "authorization" in params               # web/JWT
    assert "x_bot_token" in params                 # bot/shared-secret
    # One channel descriminator covering both bots:
    assert "x_channel" in params


# ── 2. Bot clients converge on the same call ────────────────────────────────


def _read(p: Path) -> str:
    return p.read_text()


def test_telegram_and_whatsapp_clients_target_same_endpoint():
    tg_client = _read(ROOT / "services" / "bot" / "app" / "api_client.py")
    wa_client = _read(ROOT / "services" / "bot-whatsapp" / "app" / "api_client.py")

    # Both must POST /api/v1/process/<feature>.
    assert "/api/v1/process/" in tg_client
    assert "/api/v1/process/" in wa_client


def test_both_bots_send_bot_token_and_channel_headers():
    tg = _read(ROOT / "services" / "bot" / "app" / "api_client.py")
    wa = _read(ROOT / "services" / "bot-whatsapp" / "app" / "api_client.py")

    for src in (tg, wa):
        assert "X-Bot-Token" in src
        assert "X-User-Id" in src
        # Either client must tag the channel so the API can attribute usage.
        assert "X-Channel" in src or "x-channel" in src.lower()


def test_whatsapp_client_tags_channel_as_whatsapp():
    wa = _read(ROOT / "services" / "bot-whatsapp" / "app" / "api_client.py")
    assert '"whatsapp"' in wa.lower().replace("'", '"')


# ── 3. Single source of truth for processors ───────────────────────────────


def test_no_private_processor_copies_inside_bots():
    """
    Sprint 2 moved processors into `app.processors.*`. A regression where a
    bot service re-imports e.g. `bot.processors.gst_validator` would silently
    fork the pipeline. We refuse to allow that by scanning the trees.
    """
    forbidden = {"processors/service.py", "processors/bill_to_make.py",
                 "processors/gst_validator.py", "processors/quotation_compare.py"}
    for service in ("bot", "bot-whatsapp"):
        for path in (ROOT / "services" / service).rglob("processors/*.py"):
            rel = path.relative_to(ROOT / "services" / service).as_posix()
            assert rel not in forbidden, (
                f"{service} contains a forbidden processor copy at {rel}. "
                "All processors live in `services/api/app/processors/*`."
            )


def test_process_route_routes_to_central_processors():
    """The route under test imports from `app.processors` — not from a bot."""
    src = _read(ROOT / "services" / "api" / "app" / "routes" / "process.py")
    assert "from app.processors" in src or "app.processors" in src
    for bad in ("bot.processors", "from bot ", "from bot."):
        assert bad not in src, f"process.py shouldn't import from bot: {bad}"


# ── 4. Output rendering parity: same renderer, regardless of caller ─────────


def test_sister_quote_renderer_is_channel_agnostic():
    """`_process_sister_quote` doesn't branch on `caller.channel`."""
    src = _read(ROOT / "services" / "api" / "app" / "routes" / "process.py")
    # Find the function body.
    start = src.find("def _process_sister_quote(")
    assert start >= 0
    # Cap at the next top-level def to keep the slice tight.
    end = src.find("\ndef ", start + 1)
    body = src[start:end] if end > 0 else src[start:]
    # Hard rule: no per-channel branching inside the renderer.
    assert "caller.channel" not in body, (
        "sister_quote rendering must not branch on caller.channel — "
        "that would break the parity contract from §14."
    )


# ── 5. Output schema parity ─────────────────────────────────────────────────


def test_process_response_is_channel_independent():
    from app.schemas.schemas import ProcessResponse

    fields = set(ProcessResponse.model_fields.keys())
    # No channel-specific fields leak into the response.
    assert "telegram_chat_id" not in fields
    assert "whatsapp_wa_id" not in fields
    # The core fields all channels need are present.
    assert "output_filename" in fields
    assert "parsed_data" in fields
    assert "quota" in fields
