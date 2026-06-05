#genai: Sprint 5 / WS-E — WhatsApp conversation state machine.
"""
Mirrors the Telegram bot's anchor flow but rendered as WhatsApp-native
interactions (buttons ≤3, lists ≤10, free-text fallback). All side-effects
(file processing, branding) live in the API — this file only deals with
state transitions and message rendering.

States stored in `SessionStore` (Redis-backed):

    idle              ← no file yet
    awaiting_name     ← first-time user; we asked for their business name
    file_received     ← file uploaded, waiting for the user to pick an action
    confirming        ← preview produced, waiting for ✅ / ✏️
    picking_format    ← user confirmed, choosing a saved format
    working           ← generation in flight (very short window)

Each transition writes the new state + needed scratchpad (file_bytes_b64,
preview JSON, last filename, etc.) back to the store.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from app import messages
from app.api_client import ApiError, confirm_channel_link, list_sister_formats, process_feature, register_channel
from app.bsp.base import (
    BspProvider,
    InboundMessage,
    OutboundButton,
    OutboundListItem,
    OutboundMessage,
)
from app.config import get_settings
from app.session_store import SessionStore

logger = logging.getLogger(__name__)

ACCEPTED_SUFFIXES = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".xls", ".xlsx"}
CONFIRM_TOKENS = {"✅", "yes", "y", "ok", "okay", "confirm"}
CANCEL_TOKENS = {"❌", "no", "cancel", "stop"}
EDIT_TOKENS = {"✏️", "edit"}


class Conversation:
    def __init__(self, bsp: BspProvider, store: SessionStore):
        self.bsp = bsp
        self.store = store

    # ── Entry point ─────────────────────────────────────────────────────────

    async def handle(self, msg: InboundMessage) -> None:
        """Dispatch one inbound message. Idempotent: caller already deduped."""
        # Slash commands work regardless of state.
        if msg.text:
            cmd = msg.text.strip().lower()
            if cmd in {"/help", "help"}:
                await self._reply(msg.from_e164, messages.HELP)
                return
            if cmd in {"/start", "start", "hi", "hello"}:
                await self._handle_start(msg)
                return
            if cmd.startswith("/link"):
                await self._handle_link_command(msg)
                return
            if cmd in {"/cancel", "cancel"}:
                await self.store.clear(msg.from_e164)
                await self._reply(msg.from_e164, messages.CANCELLED)
                return

        session = await self.store.get(msg.from_e164)
        step = str(session.get("step") or "idle")

        if step == "awaiting_name":
            await self._handle_business_name(msg, session)
            return

        # Outside of `awaiting_name`, every other state assumes the user is
        # already provisioned. The first message ever gets routed through
        # _handle_start which provisions on the fly.
        if "user_id" not in session and step != "awaiting_name":
            await self._handle_start(msg)
            # Re-pull session post-provisioning.
            session = await self.store.get(msg.from_e164)
            step = str(session.get("step") or "idle")

        if step == "file_received" and msg.kind == "button":
            await self._handle_action_choice(msg, session)
            return
        if step == "confirming":
            await self._handle_confirmation(msg, session)
            return
        if step == "picking_format":
            await self._handle_format_choice(msg, session)
            return

        # Media arrival is the same regardless of step (we just overwrite).
        if msg.kind == "media":
            await self._handle_file(msg, session)
            return

        # Free-text fallback.
        await self._reply(msg.from_e164, messages.UNKNOWN_CMD)

    # ── /start / first time ─────────────────────────────────────────────────

    async def _handle_start(self, msg: InboundMessage) -> None:
        """
        First-time path. We need a business name before we can provision a
        user. Telegram solves this by reading the user's TG profile name; on
        WhatsApp the BSP-provided `senderName` is unreliable, so we ask.
        """
        session = await self.store.get(msg.from_e164)
        if "user_id" in session:
            company = session.get("company_name", "your team")
            await self._reply(msg.from_e164, messages.WELCOME_BACK.format(company=company))
            session["step"] = "idle"
            await self.store.put(msg.from_e164, session)
            return

        # Brand-new user.
        session.update({"step": "awaiting_name"})
        await self.store.put(msg.from_e164, session)
        await self._reply(msg.from_e164, messages.WELCOME_FIRST)

    async def _handle_business_name(self, msg: InboundMessage, session: dict[str, Any]) -> None:
        name = (msg.text or "").strip()
        if len(name) < 2 or len(name) > 80:
            await self._reply(msg.from_e164, messages.ASK_BUSINESS_NAME_AGAIN)
            return
        try:
            auth = await register_channel(
                e164=msg.from_e164,
                name=msg.from_name or name,
                company_name=name,
            )
        except ApiError as exc:
            await self._reply(msg.from_e164, messages.ERROR_GENERIC.format(message=exc))
            return
        session.update(
            {
                "step": "idle",
                "user_id": auth["user"]["id"],
                "organization_id": auth["organization"]["id"],
                "company_name": auth["organization"]["name"],
            }
        )
        await self.store.put(msg.from_e164, session)
        await self._reply(
            msg.from_e164,
            messages.WELCOME_BACK.format(company=auth["organization"]["name"]),
        )

    # ── /link CODE — web → WhatsApp ────────────────────────────────────────

    async def _handle_link_command(self, msg: InboundMessage) -> None:
        parts = (msg.text or "").split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._reply(msg.from_e164, messages.LINK_HELP)
            return
        token = parts[1].strip()
        try:
            await confirm_channel_link(e164=msg.from_e164, token=token)
        except ApiError as exc:
            await self._reply(msg.from_e164, messages.LINK_FAIL.format(message=exc))
            return
        # Re-resolve account so subsequent messages reuse the linked user.
        session = await self.store.get(msg.from_e164)
        try:
            auth = await register_channel(
                e164=msg.from_e164,
                name=msg.from_name or "User",
                company_name=session.get("company_name") or "Your business",
            )
            session.update(
                {
                    "step": "idle",
                    "user_id": auth["user"]["id"],
                    "organization_id": auth["organization"]["id"],
                    "company_name": auth["organization"]["name"],
                }
            )
            await self.store.put(msg.from_e164, session)
            await self._reply(
                msg.from_e164,
                messages.LINK_OK.format(company=auth["organization"]["name"]),
            )
        except ApiError as exc:  # pragma: no cover — defensive
            await self._reply(msg.from_e164, messages.LINK_FAIL.format(message=exc))

    # ── File received ───────────────────────────────────────────────────────

    async def _handle_file(self, msg: InboundMessage, session: dict[str, Any]) -> None:
        media = msg.media
        if not media:
            await self._reply(msg.from_e164, messages.ACK_NON_DOC)
            return
        filename = (media.filename or "supplier-quote.pdf").lower()
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()
            if ext not in ACCEPTED_SUFFIXES:
                await self._reply(msg.from_e164, messages.ACK_NON_DOC)
                return
        max_bytes = get_settings().max_upload_bytes
        if media.size_bytes and media.size_bytes > max_bytes:
            await self._reply(
                msg.from_e164,
                f"That file is over {max_bytes // (1024 * 1024)} MB. Trim it or send a PDF.",
            )
            return

        # Download from BSP, stash in session for the confirm step.
        try:
            file_bytes, real_filename = await self.bsp.fetch_media(msg)
        except Exception as exc:
            logger.exception("media fetch failed")
            await self._reply(msg.from_e164, messages.ERROR_GENERIC.format(message=exc))
            return

        session.update(
            {
                "step": "file_received",
                "filename": real_filename,
                "file_b64": base64.b64encode(file_bytes).decode("ascii"),
                "preview": None,
                "selected_format_id": None,
            }
        )
        await self.store.put(msg.from_e164, session)

        await self._send(
            OutboundMessage(
                to_e164=msg.from_e164,
                text=messages.ACK_FILE.format(filename=real_filename),
                buttons=[
                    OutboundButton(title="Sister Quote", payload="feature:sister_quote"),
                    OutboundButton(title="Validate GST", payload="feature:gst_validate"),
                    OutboundButton(title="More", payload="feature:more"),
                ],
            )
        )

    # ── Action choice ───────────────────────────────────────────────────────

    async def _handle_action_choice(self, msg: InboundMessage, session: dict[str, Any]) -> None:
        payload = (msg.interactive_payload or "").strip()
        if payload == "feature:more":
            await self._reply(
                msg.from_e164,
                messages.WEB_INSTEAD.format(path="tools"),
            )
            return
        if payload == "feature:gst_validate":
            await self._run_single_shot(msg, session, feature="gst_validate")
            return
        if payload == "feature:sister_quote":
            await self._preview_sister_quote(msg, session)
            return
        # Unknown button — fall back to the text the user saw.
        await self._reply(msg.from_e164, messages.UNKNOWN_CMD)

    async def _preview_sister_quote(self, msg: InboundMessage, session: dict[str, Any]) -> None:
        file_b64 = session.get("file_b64")
        filename = session.get("filename") or "supplier-quote.pdf"
        if not file_b64:
            await self._reply(msg.from_e164, "Hmm — I don't have your file anymore. Drop it again?")
            session["step"] = "idle"
            await self.store.put(msg.from_e164, session)
            return
        file_bytes = base64.b64decode(file_b64)
        await self._reply(msg.from_e164, "⏳ Reading your file…")
        try:
            preview = await process_feature(
                e164=msg.from_e164,
                feature="sister_quote",
                file_bytes=file_bytes,
                filename=filename,
                mode="preview",
            )
        except ApiError as exc:
            await self._reply(msg.from_e164, _api_error_text(exc))
            return

        parsed = preview.get("parsed_data") or {}
        items: list[dict[str, Any]] = []
        for section in parsed.get("sections") or []:
            for it in section.get("items") or []:
                items.append(it)
        if not items:
            await self._reply(
                msg.from_e164,
                "I couldn't read items from this file. Open the web app to edit "
                "manually: docseva.in/new-quote",
            )
            session["step"] = "idle"
            await self.store.put(msg.from_e164, session)
            return

        session.update({"step": "confirming", "preview": parsed})
        await self.store.put(msg.from_e164, session)
        await self._send(
            OutboundMessage(
                to_e164=msg.from_e164,
                text=messages.CONFIRM_HEADER.format(
                    recipient=parsed.get("recipient_name") or "—",
                    n=len(items),
                    items=messages.format_items_block(items),
                )
                + "\n\n"
                + messages.CONFIRM_FOOTER,
                buttons=[
                    OutboundButton(title="✅ Looks good", payload="confirm:yes"),
                    OutboundButton(title="✏️ Edit on web", payload="confirm:edit"),
                    OutboundButton(title="❌ Cancel", payload="confirm:cancel"),
                ],
            )
        )

    # ── Confirm step ────────────────────────────────────────────────────────

    async def _handle_confirmation(self, msg: InboundMessage, session: dict[str, Any]) -> None:
        payload = (msg.interactive_payload or "").lower()
        text = (msg.text or "").strip().lower()
        if payload == "confirm:yes" or text in CONFIRM_TOKENS:
            await self._offer_formats(msg, session)
            return
        if payload == "confirm:edit" or text in EDIT_TOKENS:
            await self._reply(msg.from_e164, messages.WEB_INSTEAD.format(path="new-quote"))
            return
        if payload == "confirm:cancel" or text in CANCEL_TOKENS:
            await self.store.clear(msg.from_e164)
            await self._reply(msg.from_e164, messages.CANCELLED)
            return
        await self._reply(msg.from_e164, "Tap ✅ to confirm or ❌ to cancel.")

    async def _offer_formats(self, msg: InboundMessage, session: dict[str, Any]) -> None:
        try:
            formats = await list_sister_formats(msg.from_e164)
        except ApiError as exc:
            await self._reply(msg.from_e164, _api_error_text(exc))
            return
        items = [
            OutboundListItem(
                title=messages.PICK_FORMAT_DEFAULT_LABEL,
                description="Clean, neutral layout",
                payload="format:default",
            )
        ]
        for f in formats[:9]:
            items.append(
                OutboundListItem(
                    title=(f.get("name") or "Format")[:24],
                    description=(f.get("original_filename") or "")[:72],
                    payload=f"format:{f.get('id')}",
                )
            )
        session["step"] = "picking_format"
        await self.store.put(msg.from_e164, session)
        await self._send(
            OutboundMessage(
                to_e164=msg.from_e164,
                text=messages.PICK_FORMAT_HEADER,
                list_title="Choose format",
                list_button_label="Formats",
                list_items=items,
            )
        )

    # ── Format choice → final generation ────────────────────────────────────

    async def _handle_format_choice(self, msg: InboundMessage, session: dict[str, Any]) -> None:
        payload = (msg.interactive_payload or "").strip()
        text = (msg.text or "").strip().lower()
        format_id: str | None = None
        if payload.startswith("format:"):
            tail = payload.split(":", 1)[1]
            if tail and tail != "default":
                format_id = tail
        elif text == "1" or text == "default" or text == "my default":
            format_id = None
        elif text.isdigit():
            # Numeric reply (free-text fallback) — index into the saved formats list.
            idx = int(text) - 2  # 1=Default, so 2 is the first saved.
            try:
                formats = await list_sister_formats(msg.from_e164)
            except ApiError as exc:
                await self._reply(msg.from_e164, _api_error_text(exc))
                return
            if 0 <= idx < len(formats):
                format_id = formats[idx]["id"]
        else:
            await self._reply(msg.from_e164, "Reply with the number of your chosen format.")
            return

        await self._reply(msg.from_e164, messages.GENERATING)

        file_b64 = session.get("file_b64")
        filename = session.get("filename") or "supplier-quote.pdf"
        preview = session.get("preview") or {}
        if not file_b64:
            await self._reply(msg.from_e164, "I lost the file. Drop it again to retry.")
            await self.store.clear(msg.from_e164)
            return
        try:
            resp = await process_feature(
                e164=msg.from_e164,
                feature="sister_quote",
                file_bytes=base64.b64decode(file_b64),
                filename=filename,
                mode="final",
                params={"output_extension": "docx", "quote": preview},
                format_id=format_id,
            )
        except ApiError as exc:
            await self._reply(msg.from_e164, _api_error_text(exc))
            return

        quota = resp.get("quota") or {}
        used = quota.get("used", "—")
        limit = quota.get("limit", "—")

        await self._send(
            OutboundMessage(
                to_e164=msg.from_e164,
                document_url=resp.get("output_url"),
                document_filename=resp.get("output_filename"),
                document_caption=messages.DONE.format(used=used, limit=limit),
            )
        )
        # Reset to idle but keep user_id/company_name for next time.
        session.update({"step": "idle", "file_b64": None, "preview": None})
        await self.store.put(msg.from_e164, session)

    # ── GST validate + future single-shot features ─────────────────────────

    async def _run_single_shot(
        self, msg: InboundMessage, session: dict[str, Any], feature: str
    ) -> None:
        file_b64 = session.get("file_b64")
        filename = session.get("filename") or "file.pdf"
        if not file_b64:
            await self._reply(msg.from_e164, "Drop the file first, then pick an action.")
            return
        await self._reply(msg.from_e164, "⏳ Working on it…")
        try:
            resp = await process_feature(
                e164=msg.from_e164,
                feature=feature,
                file_bytes=base64.b64decode(file_b64),
                filename=filename,
                mode="final",
            )
        except ApiError as exc:
            await self._reply(msg.from_e164, _api_error_text(exc))
            return
        quota = resp.get("quota") or {}
        await self._send(
            OutboundMessage(
                to_e164=msg.from_e164,
                document_url=resp.get("output_url"),
                document_filename=resp.get("output_filename"),
                document_caption=messages.DONE.format(
                    used=quota.get("used", "—"), limit=quota.get("limit", "—")
                ),
            )
        )
        session.update({"step": "idle", "file_b64": None})
        await self.store.put(msg.from_e164, session)

    # ── Output helpers ──────────────────────────────────────────────────────

    async def _reply(self, e164: str, text: str) -> None:
        await self._send(OutboundMessage(to_e164=e164, text=text))

    async def _send(self, out: OutboundMessage) -> None:
        try:
            await self.bsp.send(out)
        except Exception as exc:
            logger.exception("bsp.send failed: %s", exc)


def _api_error_text(exc: ApiError) -> str:
    if exc.code == "E001":
        return messages.ERROR_QUOTA.format(limit="cycle")
    return messages.ERROR_GENERIC.format(message=str(exc))
