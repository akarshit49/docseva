#genai: Auth helpers — API-key validation for bot-to-API + JWT for web callers.
from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.jwt import TokenError, decode_access_token
from app.models.models import ChannelLink, User


async def verify_bot_token(x_bot_token: str = Header(...)) -> None:
    """
    FastAPI dependency — validates the shared bot API token.
    The bot service sends this token in every request as:
        X-Bot-Token: <API_BOT_TOKEN from .env>
    """
    if x_bot_token != settings.api_bot_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bot token.",
        )


@dataclass
class Caller:
    """The authenticated principal for a request — same shape for web & bot."""

    user_id: uuid.UUID
    organization_id: uuid.UUID
    channel: str  # "web" | "telegram" | "whatsapp"


def _parse_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


#genai: WS-A / WS-C — unified auth resolver.
# Order of precedence:
#   1. `Authorization: Bearer <JWT>` (web callers)
#   2. `X-Bot-Token` + `X-User-Id` + optional `X-Channel` (telegram/whatsapp bots)
# Bots prove they're "DocSeva infra" via the shared secret AND identify the end
# user via X-User-Id (their handle on the channel). The resolver looks up the
# matching `channel_links` row to find the canonical `User`.
from fastapi import Depends


async def resolve_caller(
    authorization: str | None = Header(default=None),
    x_bot_token: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
    x_channel: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> Caller:
    """Return the authenticated `Caller` or raise 401."""
    # ── Web (JWT) ────────────────────────────────────────────────────────────
    bearer = _parse_bearer(authorization)
    if bearer:
        try:
            payload = decode_access_token(bearer)
        except TokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {exc}",
            )
        try:
            user_id = uuid.UUID(payload["sub"])
            org_id = uuid.UUID(payload["org_id"])
        except (KeyError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token payload.",
            )
        return Caller(user_id=user_id, organization_id=org_id, channel="web")

    # ── Bot (shared secret + user handle) ────────────────────────────────────
    if x_bot_token and x_user_id:
        if x_bot_token != settings.api_bot_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bot token.",
            )
        channel = (x_channel or "telegram").lower()
        # Look up via channel_links first (new path).
        link_q = await db.execute(
            select(ChannelLink).where(
                ChannelLink.channel == channel,
                ChannelLink.handle == str(x_user_id),
            )
        )
        link = link_q.scalar_one_or_none()
        if link:
            return Caller(
                user_id=link.user_id,
                organization_id=link.organization_id,
                channel=channel,
            )
        # Back-compat: legacy users still keyed off `users.telegram_user_id`.
        if channel == "telegram":
            user_q = await db.execute(
                select(User).where(User.telegram_user_id == str(x_user_id))
            )
            user = user_q.scalar_one_or_none()
            if user:
                return Caller(
                    user_id=user.id,
                    organization_id=user.organization_id,
                    channel="telegram",
                )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found for that channel handle.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=(
            "Authentication required. Send either "
            "'Authorization: Bearer <jwt>' or "
            "'X-Bot-Token + X-User-Id [+ X-Channel]' headers."
        ),
    )
