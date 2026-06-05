#genai: Sprint 1 / WS-A — Channel linking endpoints.
"""
A logged-in web user can connect their Telegram or WhatsApp handle to the same
account via a short-lived `linking_token` round-trip:

    1. Web → POST /api/v1/channels/web/start-link {channel}
       Returns a token + deep link. The web app shows the deep link / code.

    2. User opens Telegram → bot reads `start=link_<token>` payload, OR
       user WhatsApps the code to our number. The bot then calls:
       POST /api/v1/channels/link  (X-Bot-Token + X-User-Id)  {token, handle, channel}
       The token resolves to a user_id; the bot supplies the handle (e164 / TG id)
       and we create the channel_links row.

Tokens live in Redis (10-minute TTL). If Redis is unavailable we fall back to
an in-process dict (fine for single-instance dev/test).
"""
from __future__ import annotations

import logging
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import Caller, resolve_caller, verify_bot_token
from app.models.models import ChannelLink, Organization, User
from app.schemas.schemas import (
    ChannelLinkConfirmRequest,
    ChannelLinkOut,
    ChannelLinkStartRequest,
    ChannelLinkStartResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/channels", tags=["channels"])

_LINK_TTL_SECONDS = 10 * 60
_LINK_KEY = "channel_link_token:{token}"


class _TokenStore:
    """Redis-first token store with in-memory fallback."""

    def __init__(self) -> None:
        self._client = None
        self._fallback: dict[str, tuple[str, str, float]] = {}

    def _redis(self):
        if self._client is not None:
            return self._client
        try:
            import redis  # type: ignore

            from app.core.config import settings

            self._client = redis.from_url(settings.redis_url, decode_responses=True)
            self._client.ping()
            return self._client
        except Exception as exc:
            logger.warning("channel-link store falling back to memory: %s", exc)
            self._client = None
            return None

    def put(self, token: str, user_id: str, channel: str) -> None:
        key = _LINK_KEY.format(token=token)
        client = self._redis()
        payload = f"{user_id}|{channel}"
        if client is not None:
            client.set(key, payload, ex=_LINK_TTL_SECONDS)
        else:
            self._fallback[key] = (user_id, channel, time.time() + _LINK_TTL_SECONDS)

    def take(self, token: str) -> Optional[tuple[str, str]]:
        key = _LINK_KEY.format(token=token)
        client = self._redis()
        if client is not None:
            raw = client.get(key)
            if raw:
                client.delete(key)
                user_id, _, channel = raw.partition("|")
                return (user_id, channel) if user_id and channel else None
            return None
        entry = self._fallback.pop(key, None)
        if not entry:
            return None
        user_id, channel, exp = entry
        if exp < time.time():
            return None
        return user_id, channel


_tokens = _TokenStore()


def _bot_deep_link(channel: str, token: str) -> str | None:
    if channel == "telegram":
        # The bot's username should come from env at deploy time; we keep this
        # generic so dev environments still get a meaningful value.
        import os

        bot = os.environ.get("TELEGRAM_BOT_USERNAME", "docseva_bot")
        return f"https://t.me/{bot}?start=link_{token}"
    if channel == "whatsapp":
        import os

        wa_number = os.environ.get("WHATSAPP_NUMBER_E164", "")
        # WA deep link format: https://wa.me/<number>?text=link <code>
        return f"https://wa.me/{wa_number}?text=link%20{token}" if wa_number else None
    return None


@router.get("", response_model=list[ChannelLinkOut])
async def list_channels(
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    """List all channel handles linked to the current user."""
    q = await db.execute(
        select(ChannelLink).where(ChannelLink.user_id == caller.user_id)
    )
    return q.scalars().all()


@router.post("/web/start-link", response_model=ChannelLinkStartResponse)
async def start_link(
    req: ChannelLinkStartRequest,
    caller: Caller = Depends(resolve_caller),
):
    """Web caller asks for a one-time token they'll relay to the bot channel."""
    if caller.channel != "web":
        raise HTTPException(
            status_code=403,
            detail="Only web sessions can initiate channel linking.",
        )
    if req.channel not in ("telegram", "whatsapp"):
        raise HTTPException(status_code=400, detail="Unsupported channel.")

    token = secrets.token_urlsafe(16)
    _tokens.put(token=token, user_id=str(caller.user_id), channel=req.channel)
    return ChannelLinkStartResponse(
        channel=req.channel,
        token=token,
        expires_in=_LINK_TTL_SECONDS,
        deep_link=_bot_deep_link(req.channel, token),
    )


@router.post(
    "/link",
    response_model=ChannelLinkOut,
    dependencies=[Depends(verify_bot_token)],
)
async def confirm_link(
    req: ChannelLinkConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Bot exchanges the user-provided token for a real channel_links row."""
    pair = _tokens.take(req.token)
    if not pair:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    user_id_str, stored_channel = pair
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Corrupted token state.")

    channel = (req.channel or stored_channel).lower()
    if channel != stored_channel:
        raise HTTPException(
            status_code=400,
            detail=f"Token was issued for '{stored_channel}', not '{channel}'.",
        )

    user_q = await db.execute(select(User).where(User.id == user_id))
    user = user_q.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User no longer exists.")

    # Upsert behaviour: if a row already exists for (channel, handle), return it.
    existing_q = await db.execute(
        select(ChannelLink).where(
            ChannelLink.channel == channel,
            ChannelLink.handle == req.handle,
        )
    )
    existing = existing_q.scalar_one_or_none()
    if existing:
        if existing.user_id != user_id:
            raise HTTPException(
                status_code=409,
                detail="That handle is already linked to a different account.",
            )
        existing.verified_at = datetime.now(tz=timezone.utc)
        await db.commit()
        await db.refresh(existing)
        return existing

    link = ChannelLink(
        user_id=user.id,
        organization_id=user.organization_id,
        channel=channel,
        handle=req.handle,
        verified_at=datetime.now(tz=timezone.utc),
    )
    db.add(link)
    # Mirror onto legacy `users.telegram_user_id` so older code paths still
    # resolve the user without consulting channel_links.
    if channel == "telegram" and not user.telegram_user_id:
        user.telegram_user_id = req.handle
    elif channel == "whatsapp" and not user.whatsapp_number:
        user.whatsapp_number = req.handle
    await db.commit()
    await db.refresh(link)
    return link


@router.delete("/{link_id}", status_code=204)
async def delete_link(
    link_id: uuid.UUID,
    caller: Caller = Depends(resolve_caller),
    db: AsyncSession = Depends(get_db),
):
    """Unlink a channel handle from the current user."""
    q = await db.execute(
        select(ChannelLink).where(
            ChannelLink.id == link_id,
            ChannelLink.user_id == caller.user_id,
        )
    )
    link = q.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Channel link not found.")
    await db.delete(link)
    await db.commit()
    return None
