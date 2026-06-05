#genai: Sprint 5 / WS-E — FastAPI router for the BSP webhook.
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.bsp import BspProvider, build_bsp
from app.conversation import Conversation
from app.session_store import SessionStore, get_session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Build the BSP + conversation lazily so tests can swap them out easily.
_bsp_singleton: BspProvider | None = None


def get_bsp() -> BspProvider:
    global _bsp_singleton
    if _bsp_singleton is None:
        _bsp_singleton = build_bsp()
    return _bsp_singleton


def set_bsp_for_tests(bsp: BspProvider) -> None:  # pragma: no cover
    global _bsp_singleton
    _bsp_singleton = bsp


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "bsp": get_bsp().name}


@router.post("/webhook")
async def webhook(
    request: Request,
    bsp: BspProvider = Depends(get_bsp),
    store: SessionStore = Depends(get_session_store),
) -> dict[str, str]:
    """
    BSPs POST inbound events here. We:
      1. Verify the provider-specific signature/secret.
      2. Parse the payload into 0+ `InboundMessage`s.
      3. Dedup by `message_id` so accidental replays are no-ops.
      4. Run the conversation state machine.
    """
    body_bytes = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    if not bsp.verify_signature(headers, body_bytes):
        logger.warning("Rejected webhook: bad signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = await request.json()
    except Exception:
        # Some BSPs send form-urlencoded — fall back to that.
        payload = dict((await request.form()).items())

    try:
        inbound = await bsp.parse_webhook(payload)
    except Exception as exc:
        logger.exception("parse_webhook failed: %s", exc)
        # We still return 200 — re-delivery loops are worse than a single drop.
        return {"status": "parse_error"}

    if not inbound:
        return {"status": "empty"}

    convo = Conversation(bsp=bsp, store=store)
    for msg in inbound:
        if await store.seen(msg.message_id):
            logger.info("Skipping duplicate webhook for message %s", msg.message_id)
            continue
        try:
            await convo.handle(msg)
        except Exception as exc:
            logger.exception("conversation.handle failed: %s", exc)
            # Don't 500 — the BSP will retry forever and DOS us.
    return {"status": "ok", "count": str(len(inbound))}
