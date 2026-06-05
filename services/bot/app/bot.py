#genai: DocSeva Telegram bot — multi-tenant, API-backed document automation.
#genai: WS-1/WS-2/WS-9/WS-10/WS-11 — Week 1 foundation changes.
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import uuid
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from app import api_client
from app.config import settings
from app.error_messages import friendly_error
from app.handlers.onboarding import handle_onboarding_text, start
from app.handlers.onboarding import store   # shared session store singleton
from app.health import get_health
from app.keyboards import (
    action_keyboard,
    comparison_count_keyboard,
    create_menu_keyboard,
    gst_rate_keyboard,
    hsn_keyboard,
    invoice_confirm_keyboard,
    items_review_keyboard,
    main_menu_keyboard,
    nav_keyboard,
    post_create_keyboard,
    price_adjust_keyboard,
    profile_keyboard,
    quotation_confirm_keyboard,
    sister_format_keyboard,
    sister_manage_keyboard,
    watermark_mode_keyboard,
)
from app.processors.formats import TargetFormat
from app.processors.renderers import render as render_quote
from app.processors.service import adjust_prices, convert_with_template, is_quote_document
from app.session_store import BotState
from app.utils import (
    format_history_date,
    is_file_size_ok,
    parse_billto_block,
    user_tmp_path,
)

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif"}
_ALL_EXTS = _IMAGE_EXTS | {".doc", ".docx", ".pdf", ".xls", ".xlsx"}
_TEMPLATE_EXTS = {".doc", ".docx", ".pdf"}
_TMP = Path("/tmp/docseva")


def _tmp_path(filename: str) -> Path:
    _TMP.mkdir(parents=True, exist_ok=True)
    return _TMP / filename


def _user_tmp(uid: str | int, filename: str) -> Path:
    """KI-15: per-user tmp path so concurrent users never overwrite each other."""
    return user_tmp_path(uid, filename, root=_TMP)


async def _safe_edit(query, text: str, **kwargs) -> None:
    """
    Edit the callback message text. Falls back to a new reply if the message
    is a document/photo (which cannot be text-edited via Telegram API).
    Also removes the inline keyboard from the original message to keep the UI clean.
    """
    try:
        await query.edit_message_text(text, **kwargs)
    except Exception:
        # Message has no editable text (e.g. it's a document) — remove keyboard first, then reply
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await query.message.reply_text(text, **kwargs)


async def _reply_error(update: Update, text: str = "❌ Something went wrong. Your session has been reset. Send /menu to continue.") -> None:
    """Best-effort error reply that never throws."""
    try:
        if update.message:
            await update.message.reply_text(text)
        elif update.callback_query:
            try:
                await update.callback_query.edit_message_text(text)
            except Exception:
                await update.callback_query.message.reply_text(text)
    except Exception:
        pass


#genai: WS-1 — upload output to MinIO before sending to user
async def _upload_output_file(uid: str, session, output_path: Path) -> str | None:
    """Upload output to MinIO. Returns file key or None on failure."""
    org_id = session.org_id
    if not org_id:
        return None
    try:
        from app.storage_client import upload_output
        doc_id = str(uuid.uuid4())
        key = await asyncio.get_event_loop().run_in_executor(
            None, lambda: upload_output(org_id, doc_id, output_path)
        )
        return key
    except Exception:
        logger.warning("Failed to upload output to MinIO for user %s", uid, exc_info=True)
        return None


#genai: WS-1/WS-9/WS-12/WS-6/WS-3 — increment quota and log document with retry, never throws
async def _log_and_increment(
    uid: str,
    feature: str,
    original_filename: str,
    output_filename: str,
    output_file_key: str | None = None,
    metadata: dict | None = None,
    input_file_key: str | None = None,
    source_document_id: str | None = None,
    document_type: str | None = None,
) -> dict | None:
    """Increment quota and log document with retry. Never throws. Returns the logged doc dict or None."""
    last_logged: dict | None = None
    for attempt in range(3):
        try:
            api_client.increment_quota(uid)
            last_logged = api_client.log_document(
                uid, feature, original_filename, output_filename,
                output_file_key=output_file_key,
                metadata=metadata,
                input_file_key=input_file_key,
                source_document_id=source_document_id,
                document_type=document_type,
            )
            return last_logged
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                logger.error(
                    "Failed to log document after 3 attempts: user=%s feature=%s",
                    uid, feature, exc_info=True,
                )
    return last_logged


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Last-resort handler — catches any exception that escapes a feature handler.
    Resets the user's session so they are never stuck, and tells them what happened.
    """
    logger.error("Unhandled exception in update %s", update, exc_info=context.error)
    if update is None or not hasattr(update, "effective_user"):
        return
    uid = str(update.effective_user.id) if update.effective_user else None
    if uid:
        store.reset(uid)
    await _reply_error(
        update,
        "❌ An unexpected error occurred and has been logged.\n"
        "Your session has been reset — send /menu to start again.",
    )


async def _require_auth(update: Update) -> bool:
    """Returns True if the user is registered; sends a prompt if not."""
    uid = str(update.effective_user.id)
    session = store.get(uid)
    if not session.is_registered:
        try:
            result = api_client.register_or_login(
                telegram_user_id=uid,
                name=update.effective_user.full_name or "User",
                company_name="My Company",
            )
            if not result["is_new"]:
                from app.handlers.onboarding import _populate_session
                _populate_session(session, result)
                return True
        except Exception:
            pass
        msg = update.message or update.callback_query.message
        await msg.reply_text("Please send /start to register first.")
        return False
    return True


async def _refresh_profile(telegram_user_id: str) -> dict:
    """Fetch latest company profile from API and return it."""
    try:
        return api_client.get_company_profile(telegram_user_id) or {}
    except Exception:
        return {}


def _check_quota(telegram_user_id: str) -> tuple[bool, str]:
    """Returns (ok, message). Consumes a quota slot on True."""
    try:
        q = api_client.get_quota(telegram_user_id)
        if not q["quota_ok"]:
            return False, (
                f"⚠️ *Quota exhausted* — you've used {q['docs_used']}/{q['docs_limit']} documents this month.\n"
                "Upgrade your plan to continue: /upgrade"
            )
        return True, ""
    except Exception:
        return True, ""  # don't block on API errors


# ── Command handlers ──────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await start(update, ctx)


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    uid = str(update.effective_user.id)
    session = store.get(uid)
    try:
        q = api_client.get_quota(uid)
    except Exception:
        q = {"plan": "free", "docs_used": 0, "docs_limit": 10}
    company = session.company_profile.get("display_name", "")
    #genai: KI fix — /create surfaced as a top-level option (button + commands list)
    #       so users without any file have a clear path forward.
    await update.message.reply_text(
        f"*DocSeva Menu* 🗂️\n\n"
        + (f"🏢 *{company}*\n" if company else "")
        + f"📊 Plan: {q.get('plan', 'free').title()} | {q.get('docs_used', 0)}/{q.get('docs_limit', 10)} docs used\n\n"
        "📎 *Send me a file* (DOC, DOCX, PDF, XLS, XLSX, or image) to start.\n"
        "✨ Or build one from scratch with /create.\n\n"
        "Commands:\n"
        "• /create — invoice / quotation from scratch\n"
        "• /settings — manage company profile\n"
        "• /formats — manage sister quotation formats\n"
        "• /history — last 10 processed files\n"
        "• /help — how to use DocSeva\n"
        "• /stop — exit current flow",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    await update.message.reply_text(
        "⚙️ *Company Settings*\nChoose what to update:",
        reply_markup=profile_keyboard(),
        parse_mode="Markdown",
    )


async def cmd_formats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """List and manage saved sister-quotation format templates."""
    if not await _require_auth(update):
        return
    uid = str(update.effective_user.id)
    try:
        formats = api_client.list_sister_formats(uid)
    except Exception:
        formats = []

    if not formats:
        await update.message.reply_text(
            "📄 *Sister Quotation Formats*\n\n"
            "No formats saved yet.\n\n"
            "To add a format, send a quotation file (PDF/DOC/DOCX) and choose *Sister Quotation* → *Add New Format*.",
            parse_mode="Markdown",
        )
        return

    lines = [f"📄 *Sister Quotation Formats* ({len(formats)}/10 used)\n"]
    for i, fmt in enumerate(formats, 1):
        lines.append(f"{i}. *{fmt['name']}* — `{fmt['original_filename']}`")
    lines.append("\nUse the buttons below to delete a format:")
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=sister_manage_keyboard(formats),
        parse_mode="Markdown",
    )


#genai: WS-1 — updated /history to show re-download links
async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    uid = str(update.effective_user.id)
    await _send_history(update.message, uid)


async def _send_history(message, uid: str) -> None:
    """Render the recent-documents list to the given Telegram message.

    Extracted so both /history (command) and the main-menu History button
    can reuse the same renderer.
    """
    try:
        docs = api_client.get_documents(uid)
    except Exception:
        docs = []

    if not docs:
        await message.reply_text("📂 No documents processed yet.")
        return

    #genai: KI fix — filenames/features contain underscores which Telegram tries
    #   to interpret as italic markers under Markdown parse_mode, breaking the
    #   send entirely. Send as plain text and put download links on inline
    #   keyboard URL buttons (which are immune to Markdown parsing).
    from app.storage_client import generate_presigned_url
    lines = ["📂 Recent Documents", ""]
    buttons: list[list] = []
    for i, d in enumerate(docs[:10], 1):
        status = "✅" if d.get("status") == "completed" else "❌"
        when = format_history_date(d.get("created_at", ""))
        fname = d.get("output_filename") or d.get("original_filename", "?")
        feature = d.get("feature", "")
        lines.append(f"{status} {i}. {fname} — {feature} — {when}")
        if d.get("output_file_key"):
            url = generate_presigned_url(settings.minio_bucket_outputs, d["output_file_key"])
            if url:
                # Button labels also avoid Markdown parsing — safe with underscores
                short = fname if len(fname) <= 32 else fname[:29] + "…"
                buttons.append([InlineKeyboardButton(f"⬇️ Download #{i} ({short})", url=url)])
    if buttons:
        lines.append("")
        lines.append("Tap a button below to download:")
    await message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        disable_web_page_preview=True,
    )


async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = str(update.effective_user.id)
    store.reset(uid)
    await update.message.reply_text("👋 Session ended. Send /start or just drop a file to begin again.")


#genai: WS-11 — concise help with learn-more buttons
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*DocSeva Help* 🤖\n\n"
        "Just send me any file and I'll show you what I can do with it!\n\n"
        "Or start with no file at all:\n"
        "• /create — build an invoice or quotation from scratch\n\n"
        "Quick commands:\n"
        "• /menu — see your quota & options\n"
        "• /settings — company profile\n"
        "• /formats — quotation templates\n"
        "• /history — recent documents\n"
        "• /stop — cancel current action",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📄 Document features", callback_data="help:docs")],
            [InlineKeyboardButton("🖼 Image features", callback_data="help:images")],
        ]),
    )


#genai: WS-11 — /upgrade handler (was a dead-end)
async def cmd_upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "💎 *Upgrade Your Plan*\n\n"
        "| Plan | Price | Docs/month |\n"
        "| Free | ₹0 | 10 |\n"
        "| Starter | ₹499/mo | 100 |\n"
        "| Pro | ₹1,499/mo | 500 |\n"
        "| Business | ₹3,999/mo | Unlimited |\n\n"
        "To upgrade, contact us:\n"
        "📧 support@docseva.in\n\n"
        "_Online payment coming soon!_",
        parse_mode="Markdown",
    )


#genai: WS-3 — entry point for create-from-scratch flows
async def cmd_create(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    uid = str(update.effective_user.id)
    store.reset(uid)  # always start fresh — abandons any in-progress flow
    await update.message.reply_text(
        "✨ *Create a New Document*\n\nWhat would you like to create?",
        reply_markup=create_menu_keyboard(),
        parse_mode="Markdown",
    )


# ── File handlers ─────────────────────────────────────────────────────────────

#genai: WS-2/WS-3 — states where we expect TEXT, not a file
_TEXT_EXPECTED_STATES = {
    BotState.WAITING_RENAME,
    BotState.WAITING_BILL_META,
    BotState.WAITING_BILL_HSN,
    BotState.WAITING_BILL_TO_DETAILS,
    BotState.WAITING_PRICE_CUSTOM,
    BotState.WAITING_CATALOG_DETAILS,
    BotState.WAITING_WATERMARK_TEXT,
    BotState.WAITING_SISTER_FORMAT_NAME,
    BotState.WAITING_COMPARISON_CUSTOM_COUNT,
    BotState.UPDATING_PROFILE_FIELD,
    BotState.CREATING_INVOICE_BILLTO,
    BotState.CREATING_INVOICE_ITEMS,
    BotState.CREATING_INVOICE_MORE_ITEMS,
    BotState.CREATING_INVOICE_HSN,
    BotState.CREATING_INVOICE_GST_CUSTOM,
    BotState.CREATING_INVOICE_GST_PERITEM,
    BotState.CREATING_INVOICE_EDIT_REFNO,
    BotState.CREATING_QUOTATION_BILLTO,
    BotState.CREATING_QUOTATION_ITEMS,
    BotState.CREATING_QUOTATION_TERMS,
    BotState.CREATING_QUOTATION_EDIT_REFNO,
}


async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not await _require_auth(update):
            return
        uid = str(update.effective_user.id)
        session = store.get(uid)

        doc = update.message.document
        if not doc:
            return

        # KI-06: reject oversize uploads with a clear message before we attempt download.
        ok_size, size_msg = is_file_size_ok(getattr(doc, "file_size", None))
        if not ok_size:
            await update.message.reply_text(size_msg)
            return

        suffix = Path(doc.file_name).suffix.lower()

        #genai: KI fix — handle logo uploads sent as documents (some Telegram
        #       clients always send images as files). Only accept image types.
        if (
            session.state == BotState.UPDATING_PROFILE_FIELD
            and session.updating_field == "logo"
        ):
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                await update.message.reply_text(
                    "⚠️ Please send your logo as an image (PNG, JPG, or WEBP)."
                )
                return
            await update.message.reply_text("⬇️ Downloading logo…")
            tg_file = await doc.get_file()
            local = _user_tmp(uid, doc.file_name)
            await tg_file.download_to_drive(str(local))
            await _save_company_logo(update, uid, session, local)
            return

        # ── Sister format template upload flow ───────────────────────────────────
        if session.state == BotState.WAITING_SISTER_FORMAT_FILE:
            await _handle_sister_format_upload(update, uid, session, doc, suffix)
            return

        # Comparison multi-file collection
        if session.state == BotState.WAITING_COMPARISON_FILES:
            await _add_comparison_file(update, ctx, uid, session, doc, suffix)
            return

        #genai: WS-2 — reject file when we expect text input
        if session.state in _TEXT_EXPECTED_STATES:
            await update.message.reply_text(
                "⚠️ I'm expecting a text response right now, not a file.\n\n"
                "Send /stop to cancel the current action and start fresh with this file.",
            )
            return

        if suffix not in _ALL_EXTS:
            await update.message.reply_text(
                f"⚠️ Unsupported file type: `{suffix}`\n"
                f"Accepted: {', '.join(sorted(_ALL_EXTS))}",
                parse_mode="Markdown",
            )
            return

        #genai: WS-2 — ask before replacing an already-loaded file
        if session.state == BotState.WAITING_ACTION and session.pending_file:
            await update.message.reply_text("⬇️ Downloading file…")
            tg_file = await doc.get_file()
            local = _user_tmp(uid, doc.file_name)
            await tg_file.download_to_drive(str(local))

            session._replacement_file = local
            session._replacement_filename = doc.file_name
            session.state = BotState.CONFIRMING_FILE_REPLACE
            await update.message.reply_text(
                f"You already have *{session.original_filename}* loaded.\n\n"
                f"Do you want to replace it with *{doc.file_name}*?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Yes, use new file", callback_data="replace:yes")],
                    [InlineKeyboardButton("❌ No, keep current", callback_data="replace:no")],
                ]),
                parse_mode="Markdown",
            )
            return

        # Download
        await update.message.reply_text("⬇️ Downloading file…")
        tg_file = await doc.get_file()
        local = _user_tmp(uid, doc.file_name)
        await tg_file.download_to_drive(str(local))

        session.pending_file = local
        session.original_filename = doc.file_name
        session.state = BotState.WAITING_ACTION

        await update.message.reply_text(
            f"📂 *{doc.file_name}* received.\n\nWhat would you like to do?",
            reply_markup=action_keyboard(suffix),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("handle_document crashed for user %s", update.effective_user.id if update.effective_user else "?")
        uid = str(update.effective_user.id) if update.effective_user else None
        if uid:
            store.reset(uid)
        await _reply_error(update)


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        if not await _require_auth(update):
            return
        uid = str(update.effective_user.id)
        session = store.get(uid)

        photo = update.message.photo[-1]  # highest resolution
        ok_size, size_msg = is_file_size_ok(getattr(photo, "file_size", None))
        if not ok_size:
            await update.message.reply_text(size_msg)
            return
        await update.message.reply_text("⬇️ Downloading image…")
        tg_file = await photo.get_file()
        fname = f"photo_{photo.file_unique_id}.jpg"
        local = _user_tmp(uid, fname)
        await tg_file.download_to_drive(str(local))

        #genai: KI fix — if the user came from /settings → "Upload Logo", treat
        #       this photo as the company logo instead of offering generic image
        #       actions (which is the broken flow they reported).
        if (
            session.state == BotState.UPDATING_PROFILE_FIELD
            and session.updating_field == "logo"
        ):
            await _save_company_logo(update, uid, session, local)
            return

        session.pending_file = local
        session.original_filename = fname
        session.state = BotState.WAITING_ACTION

        await update.message.reply_text(
            "🖼 Image received. What would you like to do?",
            reply_markup=action_keyboard(".jpg"),
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("handle_photo crashed for user %s", update.effective_user.id if update.effective_user else "?")
        uid = str(update.effective_user.id) if update.effective_user else None
        if uid:
            store.reset(uid)
        await _reply_error(update)


#genai: Save a freshly downloaded logo file to the user's company profile
#       (via the API's MinIO-backed logo endpoint) and confirm the update.
async def _save_company_logo(update: Update, uid: str, session, local_path) -> None:
    await update.message.reply_text("⬆️ Saving logo to your profile…")
    try:
        updated = await asyncio.get_event_loop().run_in_executor(
            None, lambda: api_client.upload_company_logo(uid, local_path)
        )
        if isinstance(updated, dict):
            session.company_profile.update(updated)
    except Exception:
        logger.exception("upload_company_logo failed for user %s", uid)
        session.state = BotState.IDLE
        session.updating_field = None
        await update.message.reply_text(
            "❌ Couldn't save your logo. Please try again from /settings → Upload Logo.",
            reply_markup=profile_keyboard(),
        )
        return
    finally:
        try:
            local_path.unlink(missing_ok=True)
        except Exception:
            pass

    session.state = BotState.IDLE
    session.updating_field = None
    await update.message.reply_text(
        "✅ *Logo saved!*\n\n"
        "It will now appear on your invoices, quotations and product catalogs.",
        parse_mode="Markdown",
        reply_markup=profile_keyboard(),
    )


# ── Callback query handler ────────────────────────────────────────────────────

async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass  # answer() may fail if the query is too old — that's fine, proceed anyway
    uid = str(update.effective_user.id)
    session = store.get(uid)
    data = query.data

    # ── Navigation ────────────────────────────────────────────────────────────
    if data == "action:exit":
        store.reset(uid)
        q = api_client.get_quota(uid) if session.is_registered else {"plan": "free", "docs_used": 0, "docs_limit": 10}
        company = session.company_profile.get("display_name", "")
        await _safe_edit(
            query,
            f"*DocSeva Menu* 🗂️\n\n"
            + (f"🏢 *{company}*\n" if company else "")
            + f"📊 Plan: {q.get('plan', 'free').title()} | {q.get('docs_used', 0)}/{q.get('docs_limit', 10)} docs used\n\n"
            "📎 *Send me a file* (DOC, DOCX, PDF, XLS, XLSX, or image) to start.\n"
            "✨ Or tap *Create from Scratch* below.\n\n"
            "Commands:\n"
            "• /create — invoice / quotation from scratch\n"
            "• /settings — manage company profile\n"
            "• /formats — manage sister quotation formats\n"
            "• /history — last 10 processed files\n"
            "• /help — how to use DocSeva\n"
            "• /stop — exit current flow",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    #genai: KI fix — main-menu shortcut buttons so /create is reachable
    #       with a single tap (not just by typing the command).
    if data == "menu:create":
        store.reset(uid)
        await _safe_edit(
            query,
            "✨ *Create a New Document*\n\nWhat would you like to create?",
            reply_markup=create_menu_keyboard(),
            parse_mode="Markdown",
        )
        return
    if data == "menu:settings":
        await _safe_edit(
            query,
            "⚙️ *Company Settings*\nChoose what to update:",
            reply_markup=profile_keyboard(),
            parse_mode="Markdown",
        )
        return
    if data == "menu:formats":
        try:
            formats = api_client.list_sister_formats(uid)
        except Exception:
            formats = []
        if not formats:
            await _safe_edit(
                query,
                "📄 *Sister Quotation Formats*\n\n"
                "No formats saved yet.\n\n"
                "Send a quotation file (PDF/DOC/DOCX) and choose *Sister Quotation* → *Add New Format*.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
        else:
            lines = [f"📄 *Sister Quotation Formats* ({len(formats)}/10 used)\n"]
            for i, fmt in enumerate(formats, 1):
                lines.append(f"{i}. *{fmt['name']}* — `{fmt['original_filename']}`")
            lines.append("\nUse the buttons below to delete a format:")
            await _safe_edit(
                query,
                "\n".join(lines),
                reply_markup=sister_manage_keyboard(formats),
                parse_mode="Markdown",
            )
        return
    if data == "menu:history":
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await _send_history(query.message, uid)
        return
    if data == "menu:help":
        await _safe_edit(
            query,
            "*DocSeva Help* 🤖\n\n"
            "Send any file and I'll show you what I can do with it.\n\n"
            "Or start with no file at all:\n"
            "• /create — build an invoice or quotation from scratch\n\n"
            "Quick commands:\n"
            "• /menu — your quota & options\n"
            "• /settings — company profile\n"
            "• /formats — quotation templates\n"
            "• /history — recent documents\n"
            "• /stop — cancel current action",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )
        return

    if data == "action:new_file":
        store.reset(uid)
        await _safe_edit(query, "📁 *Ready for a new file!*\n\nJust send me a DOC, DOCX, PDF, Excel, or image file.", parse_mode="Markdown")
        return

    #genai: WS-2 — go back to action menu, preserving the loaded file
    if data == "action:back_to_actions":
        if session.pending_file and session.pending_file.exists():
            session.state = BotState.WAITING_ACTION
            suffix = session.pending_file.suffix.lower()
            await _safe_edit(
                query,
                f"📂 *{session.original_filename}* is still loaded.\n\nWhat would you like to do?",
                reply_markup=action_keyboard(suffix),
                parse_mode="Markdown",
            )
        else:
            store.reset(uid)
            await _safe_edit(query, "📁 Ready for a new file!", parse_mode="Markdown")
        return

    #genai: WS-2 — file replacement confirmation
    if data == "replace:yes":
        if session._replacement_file:
            session.pending_file = session._replacement_file
            session.original_filename = session._replacement_filename
            session._replacement_file = None
            session._replacement_filename = ""
            session.state = BotState.WAITING_ACTION
            suffix = session.pending_file.suffix.lower()
            await _safe_edit(
                query,
                f"📂 *{session.original_filename}* loaded. What would you like to do?",
                reply_markup=action_keyboard(suffix),
                parse_mode="Markdown",
            )
        else:
            store.reset(uid)
            await _safe_edit(query, "📁 Ready for a new file!", parse_mode="Markdown")
        return

    if data == "replace:no":
        session._replacement_file = None
        session._replacement_filename = ""
        session.state = BotState.WAITING_ACTION
        suffix = session.pending_file.suffix.lower() if session.pending_file else ""
        await _safe_edit(
            query,
            f"📂 Keeping *{session.original_filename}*. What would you like to do?",
            reply_markup=action_keyboard(suffix),
            parse_mode="Markdown",
        )
        return

    #genai: WS-11 — help sub-menus
    if data == "help:docs":
        await _safe_edit(
            query,
            "📄 *Document Features*\n\n"
            "• *Sister Quotation* — reformat a competitor's quote in your style\n"
            "• *Bill to Make* — generate a professional invoice PDF\n"
            "• *PDF → DOCX* — extract text, preserve tables\n"
            "• *Excel → DOCX* — convert with table formatting\n"
            "• *Export to PDF* — convert any doc to PDF\n"
            "• *Rename File* — change the filename\n"
            "• *GST Validator* — check invoice math & HSN codes\n"
            "• *Quotation Comparison* — compare 2–10 quotations side-by-side",
            parse_mode="Markdown",
        )
        return

    if data == "help:images":
        await _safe_edit(
            query,
            "🖼 *Image Features*\n\n"
            "• *Add Watermark* — your company logo or custom text\n"
            "• *Remove Background* — AI-powered bg removal\n"
            "• *Product Catalog PDF* — professional single-page catalog",
            parse_mode="Markdown",
        )
        return

    # ── Profile updates ───────────────────────────────────────────────────────
    if data.startswith("profile:"):
        field = data.split(":", 1)[1]
        if field == "logo":
            session.state = BotState.UPDATING_PROFILE_FIELD
            session.updating_field = "logo"
            await query.edit_message_text("🖼 Please send your company logo as a *photo*.", parse_mode="Markdown")
        else:
            session.state = BotState.UPDATING_PROFILE_FIELD
            session.updating_field = field
            labels = {
                "display_name": "Company Name",
                "address": "Address",
                "phone": "Phone",
                "email": "Email",
                "gstin": "GSTIN",
                "bank_name": "Bank Name (include Account No & IFSC on separate lines)",
            }
            await query.edit_message_text(
                f"✏️ Enter new *{labels.get(field, field)}*:",
                parse_mode="Markdown",
            )
        return

    # ── Sister format selection / management ──────────────────────────────────
    if data == "sfmt:new":
        session.state = BotState.WAITING_SISTER_FORMAT_FILE
        await query.edit_message_text(
            "📤 *Upload Format Template*\n\n"
            "Please send a PDF, DOC, or DOCX file that shows the *format* you want your quotations converted into.\n\n"
            "This will be saved as a template your team can reuse.",
            parse_mode="Markdown",
        )
        return

    if data.startswith("sfmt:") and data != "sfmt:new":
        format_id = data.split(":", 1)[1]
        await _do_sister_quotation(query, uid, session, format_id)
        return

    if data.startswith("sfmt_del:"):
        format_id = data.split(":", 1)[1]
        await _do_delete_sister_format(query, uid, format_id)
        return

    # ── Actions ───────────────────────────────────────────────────────────────
    if not session.pending_file and data.startswith("action:"):
        await query.edit_message_text("⚠️ No file in session. Please send a file first.")
        return

    if data == "action:sister":
        await _show_sister_format_selection(query, uid, session)
        return

    if data == "action:skip_price":
        store.reset(uid)
        await _safe_edit(query, "✅ Done. Send another file or /menu.")
        return

    if data.startswith("price:"):
        await _do_price_adjust(query, uid, session, data)
        return

    if data == "action:bill_to_make":
        session.state = BotState.WAITING_BILL_META
        await query.edit_message_text(
            "🧾 *Bill to Make*\n\n"
            "Please send the *bill number and date* in this format:\n"
            "`BILL_NUMBER, DD-MM-YYYY`\n\n"
            "Example: `INV-2024-001, 31-05-2024`",
            parse_mode="Markdown",
        )
        return

    if data == "action:to_docx":
        await _do_to_docx(query, uid, session)
        return

    if data == "action:to_pdf":
        await _do_to_pdf(query, uid, session)
        return

    if data == "action:rename":
        session.state = BotState.WAITING_RENAME
        await query.edit_message_text("✏️ Enter the *new filename* (without extension):", parse_mode="Markdown")
        return

    if data == "action:watermark":
        # KI-13: ask the user how they want to watermark (logo vs text).
        profile = session.company_profile or {}
        has_logo = bool(profile.get("logo_key"))
        session.state = BotState.WAITING_WATERMARK_MODE
        await query.edit_message_text(
            "💧 *Add Watermark*\n\nChoose how to watermark this image:",
            reply_markup=watermark_mode_keyboard(has_logo=has_logo),
            parse_mode="Markdown",
        )
        return

    if data == "action:bg_remove":
        await _do_bg_remove(query, uid, session)
        return

    if data == "action:catalog":
        session.state = BotState.WAITING_CATALOG_DETAILS
        await query.edit_message_text(
            "📖 *Product Catalog*\n\n"
            "Enter item details in this format:\n"
            "`Item Name | Description (optional) | Price (optional)`\n\n"
            "Example: `Industrial Valve | High-pressure rated | ₹12,500`",
            parse_mode="Markdown",
        )
        return

    if data == "action:gst_validate":
        await _do_gst_validate(query, uid, session)
        return

    if data == "action:compare_start":
        session.state = BotState.WAITING_COMPARISON_COUNT
        await query.edit_message_text(
            "📊 *Quotation Comparison*\n\nHow many quotations do you want to compare?",
            reply_markup=comparison_count_keyboard(),
            parse_mode="Markdown",
        )
        return

    if data.startswith("cmp_n:"):
        suffix = data.split(":", 1)[1]
        if suffix == "custom":
            session.state = BotState.WAITING_COMPARISON_CUSTOM_COUNT
            await query.edit_message_text(
                "✏️ How many quotations do you want to compare?\n\n"
                "Send a number between *2* and *10*.",
                parse_mode="Markdown",
            )
            return
        n = int(suffix)
        session.comparison_total = n
        #genai: WS-12 — store as JSON-friendly string path for Redis persistence
        session.comparison_files = [
            {"path": str(session.pending_file), "name": session.original_filename, "minio_key": None}
        ]
        session.state = BotState.WAITING_COMPARISON_FILES
        store.save(uid, session)
        await query.edit_message_text(
            f"📊 Great! I have quotation 1/{n}. Please send the next {n - 1} quotation file(s) one by one.",
        )
        return

    #genai: WS-2 — skip HSN from button
    if data == "bill:skip_hsn":
        if session.pending_bill_data:
            await _bill_check_bill_to(query.message, uid, session)
        return

    # KI-13: watermark mode picker
    if data.startswith("wm:"):
        mode = data.split(":", 1)[1]
        session.pending_watermark_mode = mode
        if mode == "logo":
            await _do_watermark(query, uid, session, mode="logo")
        else:
            session.state = BotState.WAITING_WATERMARK_TEXT
            await query.edit_message_text(
                "✏️ What text should I stamp on the image?\n\n"
                "Example: `CONFIDENTIAL` or `Sample only`",
                parse_mode="Markdown",
            )
        return

    #genai: WS-3 — create-from-scratch flow callbacks
    if data.startswith("create:"):
        await _handle_create_callback(query, uid, session, data)
        return


# ── Text handler ──────────────────────────────────────────────────────────────

async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        uid = str(update.effective_user.id)
        session = store.get(uid)
        text = (update.message.text or "").strip()

        # Route to onboarding if in onboarding state
        if session.state.value.startswith("onboarding_"):
            await handle_onboarding_text(update, ctx, store)
            return

        if session.state == BotState.WAITING_SISTER_FORMAT_NAME:
            await _handle_sister_format_name(update, uid, session, text)
            return

        if session.state == BotState.WAITING_RENAME:
            await _do_rename(update, uid, session, text)
            return

        if session.state == BotState.WAITING_BILL_META:
            await _do_bill_to_make(update, uid, session, text)
            return

        if session.state == BotState.WAITING_BILL_HSN:
            await _do_bill_hsn(update, uid, session, text)
            return

        if session.state == BotState.WAITING_BILL_TO_DETAILS:
            await _do_bill_to_details(update, uid, session, text)
            return

        if session.state == BotState.WAITING_PRICE_CUSTOM:
            try:
                pct = float(text.replace("%", "").strip())
            except ValueError:
                await update.message.reply_text("Please enter a valid number, e.g. `7.5` or `-12`", parse_mode="Markdown")
                return
            await _apply_price_adjust(update, uid, session, pct)
            return

        if session.state == BotState.WAITING_CATALOG_DETAILS:
            await _do_catalog(update, uid, session, text)
            return

        if session.state == BotState.WAITING_COMPARISON_CUSTOM_COUNT:
            try:
                n = int(text.strip())
            except ValueError:
                await update.message.reply_text("⚠️ Please enter a whole number between 2 and 10.")
                return
            if not 2 <= n <= 10:
                await update.message.reply_text("⚠️ Number must be between 2 and 10.")
                return
            session.comparison_total = n
            #genai: WS-12 — store as JSON-friendly string path for Redis persistence
            session.comparison_files = [
                {"path": str(session.pending_file), "name": session.original_filename, "minio_key": None}
            ]
            session.state = BotState.WAITING_COMPARISON_FILES
            store.save(uid, session)
            await update.message.reply_text(
                f"📊 Great! I have quotation 1/{n}. Please send the next {n - 1} quotation file(s) one by one.",
            )
            return

        if session.state == BotState.WAITING_WATERMARK_TEXT:
            wm_text = text.strip()[:80] or "WATERMARK"
            await _do_watermark_text(update, uid, session, wm_text)
            return

        if session.state == BotState.UPDATING_PROFILE_FIELD:
            await _do_update_profile_field(update, uid, session, text)
            return

        #genai: WS-3 — create-from-scratch text inputs
        if session.state == BotState.CREATING_INVOICE_BILLTO:
            await _create_invoice_handle_billto(update, uid, session, text)
            return
        if session.state in (BotState.CREATING_INVOICE_ITEMS, BotState.CREATING_INVOICE_MORE_ITEMS):
            await _create_invoice_handle_items(update, uid, session, text)
            return
        if session.state == BotState.CREATING_INVOICE_HSN:
            await _create_invoice_handle_hsn(update, uid, session, text)
            return
        if session.state == BotState.CREATING_INVOICE_GST_CUSTOM:
            await _create_invoice_handle_custom_gst(update, uid, session, text)
            return
        #genai: KI fix — per-item GST + invoice ref-no override + quotation ref-no override
        if session.state == BotState.CREATING_INVOICE_GST_PERITEM:
            await _create_invoice_handle_peritem_gst(update, uid, session, text)
            return
        if session.state == BotState.CREATING_INVOICE_EDIT_REFNO:
            await _create_invoice_handle_edit_refno(update, uid, session, text)
            return
        if session.state == BotState.CREATING_QUOTATION_EDIT_REFNO:
            await _create_quotation_handle_edit_refno(update, uid, session, text)
            return
        if session.state == BotState.CREATING_QUOTATION_BILLTO:
            await _create_quotation_handle_billto(update, uid, session, text)
            return
        if session.state == BotState.CREATING_QUOTATION_ITEMS:
            await _create_quotation_handle_items(update, uid, session, text)
            return
        if session.state == BotState.CREATING_QUOTATION_TERMS:
            await _create_quotation_handle_terms(update, uid, session, text)
            return

        #genai: WS-2 — state-aware hints for unexpected text input
        _state_hints = {
            BotState.WAITING_ACTION: (
                "I'm waiting for you to choose an action.\n"
                "Tap one of the buttons on the message above, or send /stop to cancel."
            ),
            BotState.WAITING_FORMAT: (
                "Please select a format from the buttons above, or type /stop to cancel."
            ),
            BotState.WAITING_PRICE_ADJUST: (
                "Would you like to adjust prices? Tap a button above, or tap *Skip* to proceed."
            ),
            BotState.WAITING_WATERMARK_MODE: (
                "Please choose a watermark mode from the buttons above."
            ),
            BotState.WAITING_COMPARISON_COUNT: (
                "Please select how many quotations to compare from the buttons above."
            ),
            BotState.WAITING_SISTER_FORMAT_FILE: (
                "I'm waiting for a format template file (PDF, DOC, or DOCX).\n"
                "Please send the file as a document, or type /stop to cancel."
            ),
            BotState.CONFIRMING_FILE_REPLACE: (
                "Please tap one of the buttons above to confirm or cancel the file replacement."
            ),
        }

        if session.state in _state_hints:
            hint = _state_hints[session.state]
            await update.message.reply_text(hint, parse_mode="Markdown")
            return

        if session.state == BotState.WAITING_COMPARISON_FILES:
            collected = len(session.comparison_files)
            total = session.comparison_total
            hint = (
                f"I'm waiting for quotation {collected + 1} of {total}.\n"
                f"Please send a document file (DOC, DOCX, PDF, or Excel), "
                f"or type /stop to cancel the comparison."
            )
            await update.message.reply_text(hint, parse_mode="Markdown")
            return

        await update.message.reply_text(
            "📎 Send me a file (DOC, DOCX, PDF, Excel, or image) to get started, "
            "type /create to build an invoice or quotation from scratch, "
            "or /menu to see all options.",
        )
    except Exception:
        logger.exception("handle_text crashed for user %s", update.effective_user.id if update.effective_user else "?")
        uid = str(update.effective_user.id) if update.effective_user else None
        if uid:
            store.reset(uid)
        await _reply_error(update)


# ── Sister quotation — format management ──────────────────────────────────────

async def _show_sister_format_selection(query, uid: str, session) -> None:
    """Show the list of saved formats. If none, prompt to upload one first."""
    try:
        formats = api_client.list_sister_formats(uid)
    except Exception:
        formats = []

    if not formats:
        session.state = BotState.WAITING_SISTER_FORMAT_FILE
        await query.edit_message_text(
            "📤 *No Format Templates Saved Yet*\n\n"
            "To use Sister Quotation, first upload a format template — send me a PDF, DOC, or DOCX file that shows the *output style* you want.\n\n"
            "You can save up to 10 formats. Please send the template file now:",
            parse_mode="Markdown",
        )
        return

    count = len(formats)
    await query.edit_message_text(
        f"🔄 *Sister Quotation* — choose the output format ({count}/10 saved):\n\n"
        "Select a saved format to convert your document, or add a new one.",
        reply_markup=sister_format_keyboard(formats),
        parse_mode="Markdown",
    )


async def _handle_sister_format_upload(update: Update, uid: str, session, doc, suffix: str) -> None:
    """Handle the format template file upload step."""
    if suffix not in _TEMPLATE_EXTS:
        await update.message.reply_text(
            f"⚠️ Please send a PDF, DOC, or DOCX file as the format template.\n"
            f"You sent: `{suffix}`",
            parse_mode="Markdown",
        )
        return

    try:
        await update.message.reply_text("⬇️ Downloading format template…")
        tg_file = await doc.get_file()
        local = _tmp_path(f"template_{uid}{suffix}")
        await tg_file.download_to_drive(str(local))
    except Exception as exc:
        logger.exception("Failed to download sister format template")
        await update.message.reply_text(f"❌ Failed to download template: {exc}\nPlease try again.")
        store.reset(uid)
        return

    session.pending_sister_template_file = local
    session.state = BotState.WAITING_SISTER_FORMAT_NAME

    await update.message.reply_text(
        "✅ Template received!\n\n"
        "Now enter a *name* for this format so you can identify it later.\n"
        "Example: `NR Survey`, `Client A Style`, `Govt Tender Format`",
        parse_mode="Markdown",
    )


async def _handle_sister_format_name(update: Update, uid: str, session, name: str) -> None:
    """Save the format template with the given name, then let user choose the format to convert."""
    if not name or len(name) > 60:
        await update.message.reply_text(
            "⚠️ Please enter a valid name (1–60 characters).",
            parse_mode="Markdown",
        )
        return

    template_file = session.pending_sister_template_file
    if not template_file or not template_file.exists():
        await update.message.reply_text("⚠️ Template file missing. Please start over with /stop.")
        store.reset(uid)
        return

    await update.message.reply_text(f"💾 Saving format *{name}*…", parse_mode="Markdown")
    try:
        api_client.upload_sister_format(uid, name, template_file)
    except Exception as exc:
        await update.message.reply_text(f"❌ Failed to save format: {exc}")
        store.reset(uid)
        return

    count = _count_formats(uid)

    # If there is a pending input file, show the format picker so user selects a format to convert
    if session.pending_file and session.pending_file.exists():
        try:
            formats = api_client.list_sister_formats(uid)
        except Exception:
            formats = []
        session.pending_sister_template_file = None
        session.state = BotState.WAITING_ACTION
        await update.message.reply_text(
            f"✅ Format *{name}* saved! ({count}/10)\n\n"
            "Now choose which format to convert your document into:",
            parse_mode="Markdown",
            reply_markup=sister_format_keyboard(formats),
        )
    else:
        # No input file — just confirm success and return to main flow
        store.reset(uid)
        await update.message.reply_text(
            f"✅ Format *{name}* saved! ({count}/10)\n\n"
            "Send me a document file anytime to convert it using this format.\n"
            "Use /formats to manage your templates.",
            parse_mode="Markdown",
        )


def _count_formats(uid: str) -> int:
    try:
        return len(api_client.list_sister_formats(uid))
    except Exception:
        return 0


async def _do_sister_quotation(query, uid: str, session, format_id: str) -> None:
    """
    Run the sister-quotation feature via the unified /api/v1/process/sister_quote
    endpoint. The bot no longer touches MinIO or the processors directly.

    #genai: WS-D (Sprint 2) — refactored from local processor + manual MinIO
    upload to a single API call. One brain, many faces (Principle 1).
    """
    if not session.pending_file or not session.pending_file.exists():
        await query.edit_message_text("⚠️ No file in session. Please send a file first.")
        return

    ok, msg = _check_quota(uid)
    if not ok:
        await query.edit_message_text(msg, parse_mode="Markdown")
        return

    await query.edit_message_text("📖 Reading your document… (1/3)")

    stem = Path(session.original_filename).stem
    local_out = _user_tmp(uid, f"{stem}_sister.docx")

    try:
        await query.edit_message_text("🤖 Extracting items and applying your format… (2/3)")
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: api_client.process(
                telegram_user_id=uid,
                feature="sister_quote",
                file=session.pending_file,
                format_id=format_id,
                mode="final",
            ),
        )

        output_url = result.get("output_url")
        output_filename = result.get("output_filename") or local_out.name
        if not output_url:
            raise RuntimeError("API did not return an output_url.")

        await query.edit_message_text("📐 Finalising and downloading… (3/3)")
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: api_client.download_url_to(local_out, output_url),
        )

        # Keep client-side session in sync so the legacy follow-up flows
        # (price adjust, edit, etc.) still find the data they expect.
        session.pending_quote_data = result.get("parsed_data") or {}
        session.pending_quote_format = TargetFormat.SV_ENTERPRISES
        session.pending_quote_stem = stem
        session.state = BotState.WAITING_PRICE_ADJUST

        quota = result.get("quota") or {}
        used = quota.get("used")
        limit = quota.get("limit")
        quota_line = f"\n_Quota: {used}/{limit} this month._" if used is not None else ""

        await query.message.reply_document(
            document=open(local_out, "rb"),
            filename=output_filename,
            caption=(
                f"✅ Sister quotation ready!{quota_line}\n\n"
                "Would you like to adjust prices?"
            ),
            reply_markup=price_adjust_keyboard(),
        )
        await query.edit_message_text("✅ Sister quotation generated.")
    except Exception as exc:
        logger.exception("Sister quotation via /process failed")
        msg = friendly_error(exc, "sister_quotation")
        session = store.soft_reset(uid)
        try:
            await query.edit_message_text(msg, parse_mode="Markdown")
        except Exception:
            await query.message.reply_text(msg, parse_mode="Markdown")
        if session.pending_file:
            await query.message.reply_text(
                "Your file is still loaded — try another action.",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()),
            )


#genai: WS-1/WS-9/WS-10 — updated conversion with upload, retry, progress, soft_reset
async def _convert_with_format_id(
    msg_or_update,
    uid: str,
    session,
    format_id: str,
    file_key: str,
    format_name: str,
    template_local: Path,
    edit_msg=None,
) -> None:
    """Core conversion: use template to convert pending file, send result."""
    if edit_msg:
        await edit_msg.edit_message_text("📖 Reading your document… (1/4)")
    else:
        await msg_or_update.reply_text("📖 Reading your document… (1/4)")

    stem = Path(session.original_filename).stem
    out = _user_tmp(uid, f"{stem}_sister.docx")
    profile = session.company_profile

    try:
        if edit_msg:
            await edit_msg.edit_message_text("🔍 Extracting items and prices… (2/4)")

        _, quote_data = await asyncio.get_event_loop().run_in_executor(
            None, lambda: convert_with_template(session.pending_file, template_local, out, profile)
        )

        if edit_msg:
            await edit_msg.edit_message_text("📐 Applying your format template… (3/4)")

        session.pending_quote_data = quote_data
        session.pending_quote_format = TargetFormat.SV_ENTERPRISES
        session.pending_quote_stem = stem
        session.state = BotState.WAITING_PRICE_ADJUST

        if edit_msg:
            await edit_msg.edit_message_text("📄 Finalizing output… (4/4)")

        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "sister_quotation", session.original_filename, out.name, output_file_key)

        #genai: KI fix — format_name comes from the DB (often a filename with
        #       underscores) which broke Markdown parsing. Use plain text for
        #       the caption so any character is safe.
        await msg_or_update.reply_document(
            document=open(out, "rb"),
            filename=out.name,
            caption=f"✅ Sister quotation ready! (format: {format_name})\n\nWould you like to adjust prices?",
            reply_markup=price_adjust_keyboard(),
        )
        if edit_msg:
            await edit_msg.edit_message_text("✅ Sister quotation generated.")
    except Exception as exc:
        logger.exception("Sister quotation failed")
        msg = friendly_error(exc, "sister_quotation")
        session = store.soft_reset(uid)
        if session.pending_file:
            suffix = session.pending_file.suffix.lower()
            if edit_msg:
                try:
                    await edit_msg.edit_message_text(msg, parse_mode="Markdown")
                except Exception:
                    pass
            await msg_or_update.reply_text(
                msg, parse_mode="Markdown",
                reply_markup=action_keyboard(suffix),
            )
        else:
            err_text = msg
            if edit_msg:
                await edit_msg.edit_message_text(err_text, parse_mode="Markdown")
            else:
                await msg_or_update.reply_text(err_text, parse_mode="Markdown")


async def _do_delete_sister_format(query, uid: str, format_id: str) -> None:
    """Delete a sister-quotation format template."""
    try:
        api_client.delete_sister_format(uid, format_id)
    except Exception as exc:
        await query.edit_message_text(f"❌ Failed to delete: {exc}")
        return

    try:
        formats = api_client.list_sister_formats(uid)
    except Exception:
        formats = []

    if not formats:
        await query.edit_message_text(
            "🗑 Format deleted.\n\nNo formats remaining. Send a quotation file and use *Sister Quotation* to add more.",
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text(
        f"🗑 Format deleted. Remaining formats ({len(formats)}/10):",
        reply_markup=sister_manage_keyboard(formats),
        parse_mode="Markdown",
    )


# ── Price adjustment ──────────────────────────────────────────────────────────

async def _do_price_adjust(query, uid: str, session, data: str) -> None:
    # KI-05: price adjust is only valid when the previous step produced a QuoteDocument.
    if not is_quote_document(session.pending_quote_data):
        await query.edit_message_text(
            "ℹ️ Price adjustment isn't available for this output. Send a new file or /menu.",
        )
        store.reset(uid)
        return

    pct_str = data.split(":")[1]
    if pct_str == "custom":
        session.state = BotState.WAITING_PRICE_CUSTOM
        await query.edit_message_text(
            "✏️ Enter the price adjustment percentage:\n"
            "Example: `10` (increase) or `-8` (decrease)",
            parse_mode="Markdown",
        )
        return
    pct = float(pct_str)
    await _apply_price_adjust(query.message, uid, session, pct)
    await query.edit_message_text(f"✅ Prices adjusted by {pct:+.0f}%.")


async def _apply_price_adjust(msg_or_reply, uid: str, session, pct: float) -> None:
    if not session.pending_quote_data:
        return
    try:
        adjusted = await asyncio.get_event_loop().run_in_executor(
            None, lambda: adjust_prices(session.pending_quote_data, pct)
        )
        profile = session.company_profile
        out = _user_tmp(uid, f"{session.pending_quote_stem}_adjusted.docx")
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: render_quote(adjusted, session.pending_quote_format or TargetFormat.SV_ENTERPRISES, out, profile)
        )
        await msg_or_reply.reply_document(
            document=open(out, "rb"),
            filename=out.name,
            caption=f"✅ Prices adjusted by *{pct:+.1f}%*.",
            parse_mode="Markdown",
            reply_markup=nav_keyboard(),
        )
    except Exception as exc:
        logger.exception("Price adjustment failed")
        try:
            await msg_or_reply.reply_text(f"❌ Price adjustment failed: {exc}\nYour original file was already sent.")
        except Exception:
            pass
    store.reset(uid)


# ── Document processing workers ───────────────────────────────────────────────

#genai: WS-1/WS-9 — upload output, retry logging, friendly errors
async def _do_to_docx(query, uid: str, session) -> None:
    ok, msg = _check_quota(uid)
    if not ok:
        await query.edit_message_text(msg, parse_mode="Markdown")
        return
    await query.edit_message_text("⚙️ Converting to DOCX…")
    stem = Path(session.original_filename).stem
    out = _user_tmp(uid, f"{stem}.docx")
    suffix = session.pending_file.suffix.lower()
    try:
        if suffix == ".pdf":
            from app.processors.pdf_to_docx import pdf_to_docx
            await asyncio.get_event_loop().run_in_executor(None, lambda: pdf_to_docx(session.pending_file, out))
        elif suffix in {".xls", ".xlsx"}:
            from app.processors.excel_to_docx import excel_to_docx
            await asyncio.get_event_loop().run_in_executor(None, lambda: excel_to_docx(session.pending_file, out))
        else:
            await query.edit_message_text("⚠️ This format is not supported for DOCX conversion.")
            return

        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "to_docx", session.original_filename, out.name, output_file_key)

        await query.message.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
        await query.edit_message_text("✅ Converted to DOCX.")
        store.reset(uid)
    except Exception as exc:
        logger.exception("to_docx failed")
        msg = friendly_error(exc, "to_docx")
        session = store.soft_reset(uid)
        if session.pending_file:
            await query.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await query.edit_message_text(msg, parse_mode="Markdown")


async def _do_to_pdf(query, uid: str, session) -> None:
    health = get_health()
    if not health.pdf_export_ok:
        await query.edit_message_text(
            f"⚠️ PDF export is currently unavailable: {health.pdf_export_reason}\n\n"
            "Please contact support — try a different feature in the meantime.",
        )
        store.soft_reset(uid)
        return
    ok, msg = _check_quota(uid)
    if not ok:
        await query.edit_message_text(msg, parse_mode="Markdown")
        return
    await query.edit_message_text("⚙️ Exporting to PDF…")
    stem = Path(session.original_filename).stem
    out = _user_tmp(uid, f"{stem}.pdf")
    try:
        from app.processors.to_pdf import convert_to_pdf
        await asyncio.get_event_loop().run_in_executor(None, lambda: convert_to_pdf(session.pending_file, out))

        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "to_pdf", session.original_filename, out.name, output_file_key)

        await query.message.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
        await query.edit_message_text("✅ Exported to PDF.")
        store.reset(uid)
    except Exception as exc:
        logger.exception("to_pdf failed")
        msg = friendly_error(exc, "to_pdf")
        session = store.soft_reset(uid)
        if session.pending_file:
            await query.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await query.edit_message_text(msg, parse_mode="Markdown")


async def _do_rename(update: Update, uid: str, session, new_name: str) -> None:
    out_dir = _user_tmp(uid, "rename_out").parent  # per-user dir (KI-15)
    try:
        from app.processors.rename import rename_file
        out = await asyncio.get_event_loop().run_in_executor(
            None, lambda: rename_file(session.pending_file, new_name, out_dir)
        )
        await _log_and_increment(uid, "rename", session.original_filename, out.name)
        await update.message.reply_document(
            open(out, "rb"), filename=out.name, reply_markup=nav_keyboard()
        )
    except Exception as exc:
        logger.exception("rename failed")
        await update.message.reply_text(friendly_error(exc, "rename"), parse_mode="Markdown")
    store.reset(uid)


from app.utils import is_blank as _is_blank, parse_date as _parse_date

# Keep the set accessible for any direct references elsewhere in this file
_BILL_EMPTY = {"", "na", "n/a", "n.a.", "none", "unknown", "nil", "-", "not available", "not provided"}


async def _do_bill_to_make(update: Update, uid: str, session, text: str) -> None:
    try:
        parts = [p.strip() for p in text.split(",", 1)]
        if len(parts) != 2:
            raise ValueError("Wrong format")
        bill_no, raw_date = parts[0], parts[1]
    except Exception:
        await update.message.reply_text(
            "⚠️ Please use format: `BILL_NUMBER, DATE`\nExample: `INV-001, 31-05-2024`",
            parse_mode="Markdown",
        )
        return

    bill_date = _parse_date(raw_date)
    if not bill_date:
        await update.message.reply_text(
            f"⚠️ *'{raw_date}'* is not a valid date.\n\n"
            "Please re-enter the bill number and date. Accepted formats:\n"
            "`INV-001, 31-05-2024`\n"
            "`INV-001, 31/05/2024`\n"
            "`INV-001, 31.05.2024`\n"
            "`INV-001, 2024-05-31`",
            parse_mode="Markdown",
        )
        return

    ok, msg = _check_quota(uid)
    if not ok:
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    profile = await _refresh_profile(uid)
    session.company_profile.update(profile)

    #genai: WS-10 — progress indicators for bill parsing
    progress_msg = await update.message.reply_text("⏳ Reading document text… (1/4)")
    try:
        from app.processors.bill_to_make import parse_bill_doc_text
        from app.processors.extractors import extract_text
        from app.config import settings as bot_settings
        doc_text = await asyncio.get_event_loop().run_in_executor(
            None, lambda: extract_text(session.pending_file)
        )
        try:
            await progress_msg.edit_text("🤖 AI is extracting line items… (2/4)")
        except Exception:
            pass
        parsed = await asyncio.get_event_loop().run_in_executor(
            None, lambda: parse_bill_doc_text(bot_settings.openai_api_key, bot_settings.openai_model, doc_text)
        )
        try:
            await progress_msg.edit_text("🧮 Checking for missing details… (3/4)")
        except Exception:
            pass
    except Exception as exc:
        logger.exception("bill_to_make parse failed")
        msg = friendly_error(exc, "bill_to_make")
        session = store.soft_reset(uid)
        if session.pending_file:
            await update.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return

    session.pending_bill_data = {"parsed": parsed, "bill_no": bill_no, "bill_date": bill_date}
    await _bill_check_hsn(update, uid, session)


async def _bill_check_hsn(update: Update, uid: str, session) -> None:
    """Check if any items are missing HSN codes; if so, ask the user."""
    parsed = session.pending_bill_data["parsed"]
    items = parsed.get("items", [])
    missing = [
        (i, item)
        for i, item in enumerate(items)
        if _is_blank(str(item.get("hsn", "")))
    ]

    if missing:
        lines = [
            f"🔢 *HSN / SAC Codes Required* ({len(missing)} of {len(items)} items)\n",
            "The following items are missing HSN/SAC codes:",
        ]
        for i, item in missing:
            lines.append(f"  {i + 1}. {item.get('name', 'Item ' + str(i + 1))}")
        lines.append(
            "\nProvide codes using the item number (one per line):\n"
            "`1: 8481`\n`2: 998719`\n\n"
            "_Tip: provide only the numbers shown above (e.g. `1: 8481` if only item 1 is listed)_\n\n"
            "Type `skip` to leave them blank and proceed anyway."
        )
        session.state = BotState.WAITING_BILL_HSN
        #genai: WS-2 — back and cancel buttons on HSN prompt
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏭ Skip HSN codes", callback_data="bill:skip_hsn")],
                [InlineKeyboardButton("◀ Back to actions", callback_data="action:back_to_actions")],
                [InlineKeyboardButton("❌ Cancel", callback_data="action:new_file")],
            ]),
        )
    else:
        await _bill_check_bill_to(update, uid, session)


async def _do_bill_hsn(update: Update, uid: str, session, text: str) -> None:
    """Apply user-provided HSN codes, then re-validate — re-prompt for any still missing."""
    if text.strip().lower() == "skip":
        await _bill_check_bill_to(update, uid, session)
        return

    parsed = session.pending_bill_data["parsed"]
    items = parsed.get("items", [])

    applied = 0
    for line in text.splitlines():
        line = line.strip()
        if ":" in line:
            try:
                idx_str, _, code = line.partition(":")
                idx = int(idx_str.strip()) - 1
                code = code.strip()
                if 0 <= idx < len(items) and code:
                    items[idx]["hsn"] = code
                    applied += 1
            except (ValueError, IndexError):
                pass

    parsed["items"] = items
    session.pending_bill_data["parsed"] = parsed

    # Re-run the HSN check — if some are still missing it will prompt again,
    # showing only the remaining ones. If all are filled it proceeds to BillTo.
    still_missing = [
        (i, item) for i, item in enumerate(items)
        if _is_blank(str(item.get("hsn", "")))
    ]

    if still_missing:
        lines = [
            f"⚠️ *{len(still_missing)} item(s) still missing HSN codes.*\n",
            "Please provide the remaining codes:",
        ]
        for i, item in still_missing:
            lines.append(f"  {i + 1}. {item.get('name', 'Item ' + str(i + 1))}")
        lines.append(
            "\nFormat (one per line):\n"
            "`1: 8481`\n`2: 7307`\n\nType `skip` to leave them blank and proceed."
        )
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        # state stays WAITING_BILL_HSN
    else:
        await _bill_check_bill_to(update, uid, session)


async def _bill_check_bill_to(update: Update, uid: str, session) -> None:
    """Check if BillTo is complete; if not, ask the user."""
    parsed = session.pending_bill_data["parsed"]
    bill_to = parsed.get("bill_to", {})
    has_bill_to = (
        bool(bill_to.get("name", "").strip())
        and not _is_blank(bill_to.get("name", ""))
        and bool(bill_to.get("address", "").strip())
        and not _is_blank(bill_to.get("address", ""))
    )

    if not has_bill_to:
        session.state = BotState.WAITING_BILL_TO_DETAILS
        await update.message.reply_text(
            "📋 *Bill To / Ship To Details*\n\n"
            "The document doesn't contain complete billing address details. Please provide them:\n\n"
            "Send in this format (one line each):\n"
            "`Name: Company Name`\n"
            "`Address: Full Address`\n"
            "`GSTIN: 07XXXXX` *(or NA)*\n"
            "`State: State Name`\n\n"
            "Ship To defaults to Bill To unless you add:\n"
            "`ShipTo Name: ...`\n"
            "`ShipTo Address: ...`\n\n"
            "*Example:*\n"
            "`Name: ABC Pvt Ltd`\n"
            "`Address: 45 MG Road, Delhi`\n"
            "`GSTIN: 07ABCDE1234F1Z5`\n"
            "`State: Delhi`",
            parse_mode="Markdown",
        )
    else:
        await _generate_bill_pdf(update, uid, session)


async def _do_bill_to_details(update: Update, uid: str, session, text: str) -> None:
    """Parse user-provided BillTo/ShipTo details and proceed to PDF generation."""
    bill_data = session.pending_bill_data
    if not bill_data:
        await update.message.reply_text("⚠️ Session expired. Please start over.")
        store.reset(uid)
        return

    details = parse_billto_block(text)  # KI-11: case + whitespace insensitive
    name = details["name"]
    address = details["address"]
    gstin = details["gstin"] or "NA"
    state = details["state"]
    shipto_name = details["shipto_name"] or name
    shipto_addr = details["shipto_address"] or address

    if not name or not address:
        await update.message.reply_text(
            "⚠️ At minimum *Name* and *Address* are required.\n\n"
            "Example:\n`Name: ABC Pvt Ltd`\n`Address: 45 MG Road, Delhi`",
            parse_mode="Markdown",
        )
        return

    parsed = bill_data["parsed"]
    parsed["bill_to"] = {"name": name, "address": address, "gstin": gstin, "state_name": state, "state_code": ""}
    parsed["ship_to"] = {"name": shipto_name, "address": shipto_addr, "gstin": gstin, "state_name": state, "state_code": ""}
    bill_data["parsed"] = parsed
    session.pending_bill_data = bill_data

    await _generate_bill_pdf(update, uid, session)


#genai: WS-1/WS-9/WS-10 — upload output, retry, progress, soft_reset
async def _generate_bill_pdf(update, uid: str, session) -> None:
    """Render the invoice PDF and send it. Expects session.pending_bill_data to be set."""
    bill_data = session.pending_bill_data
    if not bill_data:
        await update.reply_text("⚠️ Session expired. Please start over.") if hasattr(update, "reply_text") else await update.message.reply_text("⚠️ Session expired. Please start over.")
        store.reset(uid)
        return

    msg_target = update.message if hasattr(update, "message") and update.message else update

    profile = session.company_profile
    progress_msg = await msg_target.reply_text("⏳ Generating invoice PDF… (4/4)")
    stem = Path(session.original_filename).stem
    out = _user_tmp(uid, f"{stem}_bill.pdf")

    logo_local = await _download_user_logo(uid, session)

    try:
        from app.processors.bill_to_make import generate_bill_pdf, _build_company_info
        company_info = _build_company_info(profile or {})
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_bill_pdf(
                bill_data["parsed"],
                bill_data["bill_no"],
                bill_data["bill_date"],
                out,
                company_info,
                logo_path=logo_local,
            ),
        )

        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "bill_to_make", session.original_filename, out.name, output_file_key)

        await msg_target.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
    except Exception as exc:
        logger.exception("bill_to_make failed")
        msg = friendly_error(exc, "bill_to_make")
        session = store.soft_reset(uid)
        if session.pending_file:
            await msg_target.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await msg_target.reply_text(msg, parse_mode="Markdown")
        return
    store.reset(uid)


async def _do_watermark(query, uid: str, session, mode: str = "logo", text: str | None = None) -> None:
    ok, msg = _check_quota(uid)
    if not ok:
        await query.edit_message_text(msg, parse_mode="Markdown")
        return
    await query.edit_message_text("⚙️ Adding watermark…")
    suffix = session.pending_file.suffix.lower()
    out = _user_tmp(uid, f"{session.pending_file.stem}_watermarked{suffix}")
    logo_local = await _download_user_logo(uid, session) if mode == "logo" else None
    try:
        from app.processors.watermark import add_watermark
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: add_watermark(
                session.pending_file, out,
                mode=mode, text=text, logo_path=logo_local,
            )
        )
        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "watermark", session.original_filename, out.name, output_file_key)
        await query.message.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
        await query.edit_message_text("✅ Watermark added.")
    except Exception as exc:
        logger.exception("watermark failed")
        msg = friendly_error(exc, "watermark")
        session = store.soft_reset(uid)
        if session.pending_file:
            await query.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await query.edit_message_text(msg, parse_mode="Markdown")
        return
    store.reset(uid)


async def _do_watermark_text(update: Update, uid: str, session, text: str) -> None:
    """KI-13: text-only watermark variant triggered from the WAITING_WATERMARK_TEXT state."""
    ok, msg = _check_quota(uid)
    if not ok:
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    await update.message.reply_text("⚙️ Adding text watermark…")
    suffix = session.pending_file.suffix.lower()
    out = _user_tmp(uid, f"{session.pending_file.stem}_watermarked{suffix}")
    try:
        from app.processors.watermark import add_watermark
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: add_watermark(session.pending_file, out, mode="text", text=text)
        )
        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "watermark", session.original_filename, out.name, output_file_key)
        await update.message.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
    except Exception as exc:
        logger.exception("watermark (text) failed")
        msg = friendly_error(exc, "watermark")
        session = store.soft_reset(uid)
        if session.pending_file:
            await update.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return
    store.reset(uid)


#genai: WS-12 — verify locally-cached files still exist after possible restart
async def _ensure_local_file(session) -> bool:
    """Return True if session.pending_file is still readable on disk."""
    p = session.pending_file
    if not p:
        return False
    try:
        return Path(str(p)).exists()
    except Exception:
        return False


async def _download_user_logo(uid: str, session) -> Path | None:
    """Best-effort: download the user's uploaded logo to a local path. Returns None on any failure."""
    logo_key = (session.company_profile or {}).get("logo_key")
    if not logo_key:
        return None
    try:
        from app.storage_client import download_asset
        local = _user_tmp(uid, f"logo_{uid}{Path(logo_key).suffix or '.png'}")
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: download_asset(logo_key, local)
        )
        return local if local.exists() else None
    except Exception:
        logger.exception("Failed to download user logo for %s", uid)
        return None


async def _do_bg_remove(query, uid: str, session) -> None:
    ok, msg = _check_quota(uid)
    if not ok:
        await query.edit_message_text(msg, parse_mode="Markdown")
        return
    await query.edit_message_text("⚙️ Removing background (this may take a moment)…")
    out = _user_tmp(uid, f"{session.pending_file.stem}_nobg.png")
    try:
        from app.processors.bg_remove import remove_background
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: remove_background(session.pending_file, out)
        )
        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "bg_remove", session.original_filename, out.name, output_file_key)
        await query.message.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
        await query.edit_message_text("✅ Background removed.")
    except Exception as exc:
        logger.exception("bg_remove failed")
        msg = friendly_error(exc, "bg_remove")
        session = store.soft_reset(uid)
        if session.pending_file:
            await query.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await query.edit_message_text(msg, parse_mode="Markdown")
        return
    store.reset(uid)


async def _do_catalog(update: Update, uid: str, session, text: str) -> None:
    ok, msg = _check_quota(uid)
    if not ok:
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
    parts = [p.strip() for p in text.split("|")]
    item_name = parts[0] if parts else "Product"
    description = parts[1] if len(parts) > 1 else None
    price = parts[2] if len(parts) > 2 else None

    profile = await _refresh_profile(uid)
    session.company_profile.update(profile)

    await update.message.reply_text("⚙️ Generating product catalog PDF…")
    out = _user_tmp(uid, f"{item_name}.pdf")
    #genai: KI fix — fetch the user's logo (or None) so catalog renderer
    #       skips the logo block entirely when they have not uploaded one.
    logo_local = await _download_user_logo(uid, session)
    try:
        from app.processors.catalog_pdf import generate_catalog
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_catalog(
                image_path=session.pending_file,
                output_path=out,
                item_name=item_name,
                description=description,
                price=price,
                company_profile=profile,
                logo_path=logo_local,
            ),
        )
        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "catalog_pdf", session.original_filename, out.name, output_file_key)
        await update.message.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
    except Exception as exc:
        logger.exception("catalog failed")
        msg = friendly_error(exc, "catalog_pdf")
        session = store.soft_reset(uid)
        if session.pending_file:
            await update.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
        return
    store.reset(uid)


#genai: WS-10 — progress indicators for GST validation
async def _do_gst_validate(query, uid: str, session) -> None:
    await query.edit_message_text("⏳ Reading invoice content… (1/3)")
    try:
        from app.processors.gst_validator import validate_invoice
        from app.processors.extractors import extract_text
        text = await asyncio.get_event_loop().run_in_executor(
            None, lambda: extract_text(session.pending_file)
        )
        try:
            await query.edit_message_text("🤖 AI is analyzing GST details… (2/3)")
        except Exception:
            pass
        report = await asyncio.get_event_loop().run_in_executor(
            None, lambda: validate_invoice(text)
        )
        try:
            await query.edit_message_text("✅ Checking math and HSN codes… (3/3)")
        except Exception:
            pass
        for chunk in _split_message(report):
            await query.message.reply_text(chunk, parse_mode="Markdown")
        await query.edit_message_text("✅ GST validation complete.")
    except Exception as exc:
        logger.exception("GST validate failed")
        msg = friendly_error(exc, "gst_validate")
        session = store.soft_reset(uid)
        if session.pending_file:
            await query.message.reply_text(msg, parse_mode="Markdown",
                reply_markup=action_keyboard(session.pending_file.suffix.lower()))
        else:
            await query.edit_message_text(msg, parse_mode="Markdown")
        return
    store.reset(uid)


async def _add_comparison_file(update: Update, ctx, uid: str, session, doc, suffix: str) -> None:
    if suffix not in {".doc", ".docx", ".pdf", ".xls", ".xlsx"}:
        await update.message.reply_text("⚠️ Please send a DOC, DOCX, PDF, or Excel file for comparison.")
        return

    ok_size, size_msg = is_file_size_ok(getattr(doc, "file_size", None))
    if not ok_size:
        await update.message.reply_text(size_msg)
        return

    try:
        tg_file = await doc.get_file()
        local = _user_tmp(uid, doc.file_name)
        await tg_file.download_to_drive(str(local))
    except Exception as exc:
        logger.exception("Failed to download comparison file")
        await update.message.reply_text(f"❌ Failed to download file: {exc}\nPlease try again.")
        return

    #genai: WS-12 — upload each comparison file to MinIO immediately for durability
    input_key: str | None = None
    try:
        if session.org_id:
            from app.storage_client import upload_input
            input_key = await asyncio.get_event_loop().run_in_executor(
                None, lambda: upload_input(session.org_id, str(uuid.uuid4()), local)
            )
    except Exception:
        logger.warning("Failed to upload comparison input to MinIO", exc_info=True)

    #genai: WS-12 — store path as str (Path isn't JSON-serialisable) and include MinIO key
    session.comparison_files.append({
        "path": str(local),
        "name": doc.file_name,
        "minio_key": input_key,
    })
    store.save(uid, session)

    collected = len(session.comparison_files)
    total = session.comparison_total

    if collected < total:
        await update.message.reply_text(
            f"✅ Got quotation {collected}/{total}. Please send the next one."
        )
        return

    #genai: WS-10 — progress indicators for comparison
    progress_msg = await update.message.reply_text(f"⏳ Reading {total} quotation files… (1/4)")
    out = _user_tmp(uid, "quotation_comparison.docx")
    #genai: KI fix — pass user logo (or None) so the comparison DOCX never
    #       falls back to a bundled default in production.
    logo_local = await _download_user_logo(uid, session)
    try:
        from app.processors.quotation_compare import compare_quotations
        #genai: WS-12 — coerce stored path strings back to Path objects (Redis-restored sessions)
        files = [(Path(str(f["path"])), f["name"]) for f in session.comparison_files]

        try:
            await progress_msg.edit_text("🤖 AI is extracting items from each… (2/4)")
        except Exception:
            pass

        profile_for_render = session.company_profile or {}
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: compare_quotations(
                files,
                out,
                company_profile=profile_for_render,
                logo_path=logo_local,
            ),
        )

        try:
            await progress_msg.edit_text("📊 Finalizing comparison table… (3/4)")
        except Exception:
            pass

        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(uid, "quotation_compare", f"{total} quotations", out.name, output_file_key)

        try:
            await progress_msg.edit_text("📄 Generating DOCX output… (4/4)")
        except Exception:
            pass

        await update.message.reply_document(open(out, "rb"), filename=out.name, reply_markup=nav_keyboard())
    except Exception as exc:
        logger.exception("compare failed")
        msg = friendly_error(exc, "quotation_compare")
        await update.message.reply_text(msg, parse_mode="Markdown")
    store.reset(uid)


async def _do_update_profile_field(update: Update, uid: str, session, text: str) -> None:
    field = session.updating_field
    try:
        if field == "bank_name":
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            data = {"bank_name": lines[0] if lines else text}
            if len(lines) > 1:
                data["bank_account"] = lines[1]
            if len(lines) > 2:
                data["bank_ifsc"] = lines[2]
        else:
            data = {field: text}
        updated = api_client.update_company_profile(uid, data)
        session.company_profile.update(updated)
        await update.message.reply_text(
            f"✅ *{field.replace('_', ' ').title()}* updated!",
            parse_mode="Markdown",
            reply_markup=profile_keyboard(),
        )
    except Exception as exc:
        await update.message.reply_text(f"❌ Failed to update: {exc}")
    session.state = BotState.IDLE


# ── WS-3: Create Invoice / Quotation from Scratch ────────────────────────────

#genai: WS-3 — helper: store/retrieve the in-progress create-invoice data as a plain dict
#   so the session remains JSON-serialisable for Redis (WS-12).
def _ci(session) -> dict:
    if session.pending_create_invoice is None:
        session.pending_create_invoice = {
            "bill_to": {},
            "items": [],
            "gst_rate": 18.0,
            "bill_number": "",
            "bill_date": "",
        }
    return session.pending_create_invoice


def _cq(session) -> dict:
    if session.pending_create_quotation is None:
        session.pending_create_quotation = {
            "bill_to": {},
            "items": [],
            "validity_days": 30,
            "payment_terms": "100% advance",
            "delivery_terms": "Within 7 days of order",
            "ref_no": "",
            "date": "",
        }
    return session.pending_create_quotation


async def _handle_create_callback(query, uid: str, session, data: str) -> None:
    """Dispatch for any 'create:*' callback button."""
    from datetime import datetime
    sub = data.split(":", 1)[1]

    if sub == "cancel":
        store.reset(uid)
        await _safe_edit(query, "❌ Cancelled. Send /menu when you're ready.")
        return

    if sub == "restart":
        store.reset(uid)
        await _safe_edit(
            query,
            "✨ *Create a New Document*\n\nWhat would you like to create?",
            reply_markup=create_menu_keyboard(),
            parse_mode="Markdown",
        )
        return

    if sub == "invoice":
        session.pending_create_invoice = None
        _ci(session)
        session.state = BotState.CREATING_INVOICE_BILLTO
        store.save(uid, session)
        await _safe_edit(
            query,
            "🧾 *Create Invoice*\n\n"
            "I'll walk you through it step by step.\n"
            "Your company details will be auto-filled from your profile.\n\n"
            "*Step 1/5 — Bill To (Customer)*\n\n"
            "Send the customer details in this format:\n"
            "```\n"
            "Name: Customer Company Name\n"
            "Address: Full postal address\n"
            "GSTIN: GSTIN or NA\n"
            "State: State name\n"
            "```\n"
            "_(Type /stop to cancel anytime)_",
            parse_mode="Markdown",
        )
        return

    if sub == "quotation":
        session.pending_create_quotation = None
        _cq(session)
        session.state = BotState.CREATING_QUOTATION_BILLTO
        store.save(uid, session)
        await _safe_edit(
            query,
            "📋 *Create Quotation*\n\n"
            "*Step 1/4 — Customer*\n\n"
            "Send the customer details:\n"
            "```\n"
            "Name: Customer Company Name\n"
            "Address: Full postal address\n"
            "GSTIN: GSTIN or NA (optional)\n"
            "State: State name (optional)\n"
            "```\n"
            "_(Type /stop to cancel)_",
            parse_mode="Markdown",
        )
        return

    if sub == "add_more":
        session.state = BotState.CREATING_INVOICE_MORE_ITEMS
        store.save(uid, session)
        await _safe_edit(
            query,
            "➕ Send the next batch of items (one per line):\n"
            "`Name | Qty | Price | HSN (optional)`",
            parse_mode="Markdown",
        )
        return

    if sub == "continue":
        await _create_invoice_advance_to_hsn(query.message, uid, session)
        return

    if sub == "hsn_skip":
        await _create_invoice_advance_to_gst(query.message, uid, session)
        return

    if sub == "hsn_back":
        session.state = BotState.CREATING_INVOICE_ITEMS
        store.save(uid, session)
        from app.processors.create_invoice import format_items_table
        await _safe_edit(
            query,
            f"⬅️ Back to items.\n\n{format_items_table(_ci(session)['items'])}",
            reply_markup=items_review_keyboard(),
            parse_mode="Markdown",
        )
        return

    if sub == "gst_back":
        await _create_invoice_advance_to_hsn(query.message, uid, session, edit_query=query)
        return

    if sub == "confirm_back":
        if session.state == BotState.CREATING_QUOTATION_CONFIRM:
            session.state = BotState.CREATING_QUOTATION_TERMS
            store.save(uid, session)
            await _safe_edit(
                query,
                "⬅️ Send terms again (or just type `default` to reuse defaults):\n"
                "```\n"
                "Validity: 30 days\n"
                "Payment: 100% advance\n"
                "Delivery: Within 7 days\n"
                "```",
                parse_mode="Markdown",
            )
        else:
            session.state = BotState.CREATING_INVOICE_GST_TYPE
            store.save(uid, session)
            await _safe_edit(
                query,
                "*Step 4/5 — GST Rate*\n\nSelect the GST rate for this invoice:",
                reply_markup=gst_rate_keyboard(),
                parse_mode="Markdown",
            )
        return

    if sub.startswith("gst:"):
        rate_str = sub.split(":", 1)[1]
        if rate_str == "custom":
            session.state = BotState.CREATING_INVOICE_GST_CUSTOM
            store.save(uid, session)
            await _safe_edit(
                query,
                "✏️ Enter the custom GST rate (just the number).\n"
                "Example: `7.5` for 7.5%",
                parse_mode="Markdown",
            )
            return
        if rate_str == "per_item":
            #genai: KI fix — switch into the per-item GST sub-flow
            await _create_invoice_start_peritem_gst(query.message, uid, session, edit_query=query)
            return
        try:
            rate = float(rate_str)
        except ValueError:
            return
        ci = _ci(session)
        ci["gst_rate"] = rate
        # Uniform rate — clear any per-item override so it really is uniform
        for it in ci["items"]:
            it.pop("gst_rate", None)
            it.pop("_gst_explicit", None)
        await _create_invoice_show_confirm(query.message, uid, session, edit_query=query)
        return

    #genai: KI fix — invoice/quotation reference-number override
    if sub == "edit_refno":
        session.state = BotState.CREATING_INVOICE_EDIT_REFNO
        store.save(uid, session)
        current = _ci(session).get("bill_number", "")
        await _safe_edit(
            query,
            f"✏️ *Change Invoice #*\n\nCurrent: `{current}`\n\n"
            "Send a new invoice number, or send `default` to keep the auto-generated one.\n"
            "Example: `BT-INV-042` or `2026/04/001`",
            parse_mode="Markdown",
        )
        return

    if sub == "edit_refno_q":
        session.state = BotState.CREATING_QUOTATION_EDIT_REFNO
        store.save(uid, session)
        current = _cq(session).get("ref_no", "")
        await _safe_edit(
            query,
            f"✏️ *Change Ref #*\n\nCurrent: `{current}`\n\n"
            "Send a new reference number, or send `default` to keep the auto-generated one.\n"
            "Example: `BT-Q-2026-001`",
            parse_mode="Markdown",
        )
        return

    if sub == "generate":
        await _create_invoice_generate(query.message, uid, session)
        return

    if sub == "generate_q":
        await _create_quotation_generate(query.message, uid, session)
        return


# ── Invoice text-input handlers ──────────────────────────────────────────────

async def _create_invoice_handle_billto(update: Update, uid: str, session, text: str) -> None:
    from app.processors.create_invoice import parse_customer_block
    parsed, missing = parse_customer_block(text)
    if missing:
        await update.message.reply_text(
            f"⚠️ Missing required field(s): *{', '.join(missing)}*.\n\n"
            "Please send the customer details again. Example:\n"
            "```\n"
            "Name: ABC Pvt Ltd\n"
            "Address: 12 MG Road, Delhi\n"
            "GSTIN: 07ABCDE1234F1Z5\n"
            "State: Delhi\n"
            "```",
            parse_mode="Markdown",
        )
        return

    ci = _ci(session)
    ci["bill_to"] = {
        "name": parsed.get("name", ""),
        "address": parsed.get("address", ""),
        "gstin": parsed.get("gstin", ""),
        "state": parsed.get("state", ""),
    }
    session.state = BotState.CREATING_INVOICE_ITEMS
    store.save(uid, session)

    await update.message.reply_text(
        f"✅ *Customer:* {ci['bill_to']['name']}\n"
        f"📍 {ci['bill_to']['address']}\n"
        + (f"🔢 GSTIN: {ci['bill_to']['gstin']}\n" if ci['bill_to']['gstin'] else "")
        + "\n*Step 2/5 — Add Items*\n\n"
        "Send items one per line in this format:\n"
        "`Name | Qty | Unit Price | HSN (optional)`\n\n"
        "Example:\n"
        "```\n"
        "Digital Thermometer | 2 | 4500 | 9025\n"
        "pH Meter | 1 | 12000 | 9027\n"
        "Calibration Service | 1 | 2000\n"
        "```",
        parse_mode="Markdown",
    )


async def _create_invoice_handle_items(update: Update, uid: str, session, text: str) -> None:
    from app.processors.create_invoice import parse_invoice_items, format_items_table
    new_items, errors = parse_invoice_items(text)

    if not new_items and errors:
        await update.message.reply_text(
            "⚠️ I couldn't parse any items. Issues:\n• " + "\n• ".join(errors[:5]) +
            "\n\nFormat: `Name | Qty | Unit Price | HSN (optional)`",
            parse_mode="Markdown",
        )
        return

    ci = _ci(session)
    if session.state == BotState.CREATING_INVOICE_MORE_ITEMS:
        ci["items"].extend(new_items)
    else:
        ci["items"] = new_items

    session.state = BotState.CREATING_INVOICE_ITEMS  # back to review
    store.save(uid, session)

    msg = f"✅ *{len(ci['items'])} items in this invoice:*\n\n{format_items_table(ci['items'])}"
    if errors:
        msg += "\n\n⚠️ Skipped lines:\n• " + "\n• ".join(errors[:5])

    await update.message.reply_text(
        msg,
        reply_markup=items_review_keyboard(),
        parse_mode="Markdown",
    )


async def _create_invoice_advance_to_hsn(msg_target, uid: str, session, edit_query=None) -> None:
    ci = _ci(session)
    items = ci["items"]
    missing = [i + 1 for i, it in enumerate(items) if not it.get("hsn", "").strip()]
    if not missing:
        await _create_invoice_advance_to_gst(msg_target, uid, session, edit_query=edit_query)
        return

    sample = "\n".join(f"{i}: 9999" for i in missing[:3])
    text = (
        "*Step 3/5 — HSN / SAC Codes*\n\n"
        f"⚠️ {len(missing)} item(s) are missing HSN/SAC codes (#{', #'.join(map(str, missing))}).\n\n"
        "Send the codes in `n: code` format, one per line:\n"
        f"```\n{sample}\n```\n"
        "Or tap *Skip* to leave them blank."
    )
    session.state = BotState.CREATING_INVOICE_HSN
    store.save(uid, session)
    if edit_query is not None:
        await _safe_edit(edit_query, text, reply_markup=hsn_keyboard(), parse_mode="Markdown")
    else:
        await msg_target.reply_text(text, reply_markup=hsn_keyboard(), parse_mode="Markdown")


async def _create_invoice_handle_hsn(update: Update, uid: str, session, text: str) -> None:
    from app.processors.create_invoice import parse_hsn_response
    ci = _ci(session)
    updated, missing = parse_hsn_response(text, ci["items"])
    ci["items"] = updated
    store.save(uid, session)

    if missing:
        await update.message.reply_text(
            f"Got it. Still missing HSN for #{', #'.join(map(str, missing))}.\n"
            "Send more, or tap *Skip* below.",
            reply_markup=hsn_keyboard(),
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text("✅ All items have HSN/SAC codes.")
    await _create_invoice_advance_to_gst(update.message, uid, session)


async def _create_invoice_advance_to_gst(msg_target, uid: str, session, edit_query=None) -> None:
    session.state = BotState.CREATING_INVOICE_GST_TYPE
    store.save(uid, session)
    text = "*Step 4/5 — GST Rate*\n\nSelect the GST rate for this invoice:"
    if edit_query is not None:
        await _safe_edit(edit_query, text, reply_markup=gst_rate_keyboard(), parse_mode="Markdown")
    else:
        await msg_target.reply_text(text, reply_markup=gst_rate_keyboard(), parse_mode="Markdown")


async def _create_invoice_handle_custom_gst(update: Update, uid: str, session, text: str) -> None:
    try:
        rate = float(text.replace("%", "").strip())
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g. `7.5`).", parse_mode="Markdown")
        return
    if rate < 0 or rate > 100:
        await update.message.reply_text("⚠️ Rate must be between 0 and 100.")
        return
    ci = _ci(session)
    ci["gst_rate"] = rate
    # Uniform custom rate — clear per-item overrides so it really is uniform
    for it in ci["items"]:
        it.pop("gst_rate", None)
        it.pop("_gst_explicit", None)
    await _create_invoice_show_confirm(update.message, uid, session)


#genai: KI fix — per-item GST sub-flow (prompt + handler)
async def _create_invoice_start_peritem_gst(msg_target, uid: str, session, edit_query=None) -> None:
    ci = _ci(session)
    # Reset previous explicit markers so the user starts from a clean slate
    for it in ci["items"]:
        it.pop("_gst_explicit", None)
    session.state = BotState.CREATING_INVOICE_GST_PERITEM
    store.save(uid, session)

    sample = "\n".join(f"{i+1}: 18" for i in range(min(3, len(ci["items"]))))
    text = (
        "*🎚 Per-Item GST Rates*\n\n"
        "Send the GST rate for each item in `n: rate` format, one per line:\n"
        f"```\n{sample}\n```\n"
        f"You have *{len(ci['items'])}* items. Cover all of them — you can send them in multiple messages.\n\n"
        "_Valid rates: 0–100 (no % sign needed)._"
    )
    if edit_query is not None:
        await _safe_edit(edit_query, text, parse_mode="Markdown")
    else:
        await msg_target.reply_text(text, parse_mode="Markdown")


async def _create_invoice_handle_peritem_gst(update: Update, uid: str, session, text: str) -> None:
    from app.processors.create_invoice import parse_per_item_gst
    ci = _ci(session)
    updated, missing, errors = parse_per_item_gst(text, ci["items"])
    ci["items"] = updated
    store.save(uid, session)

    if errors:
        await update.message.reply_text(
            "⚠️ Some lines were skipped:\n• " + "\n• ".join(errors[:5]),
            parse_mode="Markdown",
        )

    if missing:
        await update.message.reply_text(
            f"Got it. Still need rates for item #{', #'.join(map(str, missing))}.\n"
            "Send `n: rate` lines for the remaining items.",
            parse_mode="Markdown",
        )
        return

    # All items now have an explicit rate — preview and continue
    await update.message.reply_text("✅ All items have GST rates set.")
    await _create_invoice_show_confirm(update.message, uid, session)


#genai: KI fix — accept a user-supplied invoice / quotation number override
async def _create_invoice_handle_edit_refno(update: Update, uid: str, session, text: str) -> None:
    new_ref = text.strip()
    if new_ref.lower() != "default" and new_ref:
        # Strip any obviously dangerous chars but keep slashes/hyphens/dots/underscores
        cleaned = "".join(ch for ch in new_ref if ch.isalnum() or ch in "-_/.#")[:40]
        if cleaned:
            _ci(session)["bill_number"] = cleaned
            _ci(session)["bill_number_override"] = True
            await update.message.reply_text(f"✅ Invoice # set to `{cleaned}`", parse_mode="Markdown")
    await _create_invoice_show_confirm(update.message, uid, session)


async def _create_quotation_handle_edit_refno(update: Update, uid: str, session, text: str) -> None:
    new_ref = text.strip()
    if new_ref.lower() != "default" and new_ref:
        cleaned = "".join(ch for ch in new_ref if ch.isalnum() or ch in "-_/.#")[:40]
        if cleaned:
            _cq(session)["ref_no"] = cleaned
            _cq(session)["ref_no_override"] = True
            await update.message.reply_text(f"✅ Ref # set to `{cleaned}`", parse_mode="Markdown")
    await _create_quotation_show_confirm(update.message, uid, session)


async def _create_invoice_show_confirm(msg_target, uid: str, session, edit_query=None) -> None:
    from datetime import datetime
    from app.processors.create_invoice import compute_totals, amount_in_words

    ci = _ci(session)

    # Resolve invoice number using the profile counter — preview only, not incremented yet
    profile = session.company_profile or await _refresh_profile(uid)
    session.company_profile = profile
    #genai: KI fix — only auto-generate the invoice number when the user hasn't
    #       overridden it via the "Change Invoice #" button.
    if not ci.get("bill_number_override"):
        prefix = (profile.get("invoice_prefix") or "INV").strip() or "INV"
        counter = int(profile.get("invoice_counter") or 1)
        ci["bill_number"] = f"{prefix}-{counter:04d}"
    if not ci.get("bill_date"):
        ci["bill_date"] = datetime.now().strftime("%d-%m-%Y")

    totals = compute_totals(ci["items"], ci["gst_rate"])

    gst_breakdown_text = ""
    for b in totals["gst_breakdown"]:
        gst_breakdown_text += f"🏛 GST @{b['rate']:g}%: ₹{b['tax']:,.2f}\n"

    bt = ci["bill_to"]
    text = (
        "*Step 5/5 — Review & Generate*\n\n"
        "🧾 *Invoice Summary*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Invoice #: `{ci['bill_number']}`\n"
        f"📅 Date: {ci['bill_date']}\n\n"
        f"👤 *Bill To:* {bt['name']}\n"
        f"📍 {bt['address']}\n"
        + (f"🔢 GSTIN: {bt['gstin']}\n" if bt.get('gstin') else "")
        + f"\n📦 *Items:* {len(ci['items'])}\n"
        f"💰 Subtotal: ₹{totals['subtotal']:,.2f}\n"
        f"{gst_breakdown_text}"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 *Total: ₹{totals['total']:,.2f}*\n\n"
        f"_({amount_in_words(totals['total'])})_"
    )
    session.state = BotState.CREATING_INVOICE_CONFIRM
    store.save(uid, session)
    if edit_query is not None:
        await _safe_edit(edit_query, text, reply_markup=invoice_confirm_keyboard(), parse_mode="Markdown")
    else:
        await msg_target.reply_text(text, reply_markup=invoice_confirm_keyboard(), parse_mode="Markdown")


async def _create_invoice_generate(msg_target, uid: str, session) -> None:
    ok, qmsg = _check_quota(uid)
    if not ok:
        await msg_target.reply_text(qmsg, parse_mode="Markdown")
        return

    ci = _ci(session)
    if not ci["items"] or not ci["bill_to"].get("name"):
        await msg_target.reply_text("⚠️ Missing data. Please /create again.")
        store.reset(uid)
        return

    progress = await msg_target.reply_text("⏳ Generating invoice PDF... (1/2)")

    profile = session.company_profile or await _refresh_profile(uid)
    session.company_profile = profile

    #genai: WS-3 — atomic counter increment via API; falls back to preview if API fails
    #       KI fix — preserve the user's override; only increment+rewrite when auto-generated
    if not ci.get("bill_number_override"):
        try:
            new_counter = api_client.increment_counter(uid, "invoice")
            prefix = (profile.get("invoice_prefix") or "INV").strip() or "INV"
            ci["bill_number"] = f"{prefix}-{new_counter:04d}"
            profile["invoice_counter"] = new_counter
        except Exception:
            logger.warning("increment_counter failed; falling back to preview number %s", ci.get("bill_number"))

    out = _user_tmp(uid, f"{ci['bill_number']}_invoice.pdf")

    try:
        try:
            await progress.edit_text("⚙️ Applying company branding... (2/2)")
        except Exception:
            pass

        from app.processors.bill_to_make import generate_bill_pdf, _build_company_info
        from app.processors.create_invoice import build_invoice_data
        data = build_invoice_data(ci["bill_to"], ci["items"], ci["gst_rate"])
        company_info = _build_company_info(profile or {})
        logo_local = await _download_user_logo(uid, session)

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_bill_pdf(
                data,
                ci["bill_number"],
                ci["bill_date"],
                out,
                company_info,
                logo_path=logo_local,
            ),
        )

        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(
            uid,
            feature="create_invoice",
            original_filename=f"(scratch) {ci['bill_to'].get('name','')[:40]}",
            output_filename=out.name,
            output_file_key=output_file_key,
            metadata={"bill_number": ci["bill_number"], "items_count": len(ci["items"]),
                      "total": float(data.get("total", 0)) if isinstance(data, dict) else 0,
                      "gst_rate": ci["gst_rate"]},
            document_type="invoice",
        )

        await msg_target.reply_document(open(out, "rb"), filename=out.name)
        await msg_target.reply_text(
            f"✅ *Invoice {ci['bill_number']} generated!*\n\nWhat next?",
            reply_markup=post_create_keyboard(),
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.exception("create_invoice generation failed")
        await msg_target.reply_text(
            friendly_error(exc, "create_invoice"),
            parse_mode="Markdown",
            reply_markup=invoice_confirm_keyboard(),
        )
        return
    finally:
        try:
            await progress.delete()
        except Exception:
            pass

    store.reset(uid)


# ── Quotation text-input handlers ────────────────────────────────────────────

async def _create_quotation_handle_billto(update: Update, uid: str, session, text: str) -> None:
    from app.processors.create_invoice import parse_customer_block
    parsed, missing = parse_customer_block(text)
    if missing:
        await update.message.reply_text(
            f"⚠️ Missing required field(s): *{', '.join(missing)}*.",
            parse_mode="Markdown",
        )
        return
    cq = _cq(session)
    cq["bill_to"] = {
        "name": parsed.get("name", ""),
        "address": parsed.get("address", ""),
        "gstin": parsed.get("gstin", ""),
        "state": parsed.get("state", ""),
    }
    session.state = BotState.CREATING_QUOTATION_ITEMS
    store.save(uid, session)
    await update.message.reply_text(
        f"✅ *Customer:* {cq['bill_to']['name']}\n\n"
        "*Step 2/4 — Add Items*\n\n"
        "Send items one per line:\n"
        "`Name | Qty | Unit Price`\n\n"
        "Example:\n"
        "```\n"
        "Site Survey | 1 | 25000\n"
        "Annual Service Contract | 1 | 60000\n"
        "```",
        parse_mode="Markdown",
    )


async def _create_quotation_handle_items(update: Update, uid: str, session, text: str) -> None:
    from app.processors.create_invoice import parse_invoice_items, format_items_table
    items, errors = parse_invoice_items(text)
    if not items:
        await update.message.reply_text(
            "⚠️ I couldn't parse any items.\nFormat: `Name | Qty | Unit Price`",
            parse_mode="Markdown",
        )
        return
    cq = _cq(session)
    cq["items"] = items
    session.state = BotState.CREATING_QUOTATION_TERMS
    store.save(uid, session)
    msg = f"✅ *{len(items)} items added:*\n\n{format_items_table(items)}\n\n"
    msg += (
        "*Step 3/4 — Terms*\n\n"
        "Send your terms (or just type `default`):\n"
        "```\n"
        "Validity: 30 days\n"
        "Payment: 100% advance\n"
        "Delivery: Within 7 days\n"
        "```"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def _create_quotation_handle_terms(update: Update, uid: str, session, text: str) -> None:
    cq = _cq(session)
    if text.strip().lower() != "default":
        for line in text.strip().splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            k = key.strip().lower()
            v = val.strip()
            if not v:
                continue
            if k.startswith("valid"):
                try:
                    cq["validity_days"] = int(''.join(ch for ch in v if ch.isdigit()) or "30")
                except ValueError:
                    pass
            elif k.startswith("payment"):
                cq["payment_terms"] = v
            elif k.startswith("delivery") or k.startswith("lead"):
                cq["delivery_terms"] = v

    await _create_quotation_show_confirm(update.message, uid, session)


async def _create_quotation_show_confirm(msg_target, uid: str, session, edit_query=None) -> None:
    from datetime import datetime, timedelta
    from app.processors.create_invoice import compute_totals

    cq = _cq(session)
    profile = session.company_profile or await _refresh_profile(uid)
    session.company_profile = profile

    #genai: KI fix — only auto-generate the quotation ref when the user has not
    #       overridden it via the "Change Ref #" button.
    if not cq.get("ref_no_override"):
        prefix = (profile.get("quotation_prefix") or "QT").strip() or "QT"
        counter = int(profile.get("quotation_counter") or 1)
        cq["ref_no"] = f"{prefix}-{counter:04d}"
    cq["date"] = datetime.now().strftime("%d/%m/%Y")
    valid_until_dt = datetime.now() + timedelta(days=int(cq["validity_days"]))
    cq["valid_until"] = valid_until_dt.strftime("%d/%m/%Y")

    totals = compute_totals(cq["items"], 0)
    bt = cq["bill_to"]
    text = (
        "*Step 4/4 — Review & Generate*\n\n"
        "📋 *Quotation Summary*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 Ref #: `{cq['ref_no']}`\n"
        f"📅 Date: {cq['date']}\n"
        f"⏰ Valid until: {cq['valid_until']}\n\n"
        f"👤 *To:* {bt['name']}\n"
        f"📍 {bt['address']}\n\n"
        f"📦 *Items:* {len(cq['items'])}\n"
        f"💰 Total: ₹{totals['total']:,.2f}\n\n"
        f"📜 Validity: {cq['validity_days']} days\n"
        f"💳 Payment: {cq['payment_terms']}\n"
        f"🚚 Delivery: {cq['delivery_terms']}"
    )
    session.state = BotState.CREATING_QUOTATION_CONFIRM
    store.save(uid, session)
    if edit_query is not None:
        await _safe_edit(edit_query, text, reply_markup=quotation_confirm_keyboard(), parse_mode="Markdown")
    else:
        await msg_target.reply_text(text, reply_markup=quotation_confirm_keyboard(), parse_mode="Markdown")


async def _create_quotation_generate(msg_target, uid: str, session) -> None:
    ok, qmsg = _check_quota(uid)
    if not ok:
        await msg_target.reply_text(qmsg, parse_mode="Markdown")
        return

    cq = _cq(session)
    if not cq["items"] or not cq["bill_to"].get("name"):
        await msg_target.reply_text("⚠️ Missing data. Please /create again.")
        store.reset(uid)
        return

    progress = await msg_target.reply_text("⏳ Generating quotation DOCX... (1/2)")

    profile = session.company_profile or await _refresh_profile(uid)
    session.company_profile = profile

    #genai: KI fix — preserve user override; only auto-bump counter otherwise
    if not cq.get("ref_no_override"):
        try:
            new_counter = api_client.increment_counter(uid, "quotation")
            prefix = (profile.get("quotation_prefix") or "QT").strip() or "QT"
            cq["ref_no"] = f"{prefix}-{new_counter:04d}"
            profile["quotation_counter"] = new_counter
        except Exception:
            logger.warning("increment_counter (quotation) failed; using preview ref %s", cq.get("ref_no"))

    out = _user_tmp(uid, f"{cq['ref_no']}_quotation.docx")
    try:
        try:
            await progress.edit_text("⚙️ Applying company branding... (2/2)")
        except Exception:
            pass

        from app.processors.create_invoice import build_quotation_document
        quote = build_quotation_document(
            cq["bill_to"],
            cq["items"],
            cq["ref_no"],
            cq["date"],
            cq["valid_until"],
            subject="Quotation",
        )
        #genai: KI fix — terms render as a bullet list after the items table
        #       (no more sham "Terms" section inside the items table). The GST
        #       applicability note is always included since the quotation
        #       itself doesn't carry tax — it materialises only at billing.
        quote.terms_list = [
            f"Validity: {cq['validity_days']} days",
            f"Payment: {cq['payment_terms']}",
            f"Delivery: {cq['delivery_terms']}",
            "GST will be applicable at the time of invoice as per the prevailing rates.",
        ]

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: render_quote(quote, TargetFormat.SV_ENTERPRISES, out, profile or {}),
        )

        output_file_key = await _upload_output_file(uid, session, out)
        await _log_and_increment(
            uid,
            feature="create_quotation",
            original_filename=f"(scratch) {cq['bill_to'].get('name','')[:40]}",
            output_filename=out.name,
            output_file_key=output_file_key,
            metadata={"ref_no": cq["ref_no"], "items_count": len(cq["items"]),
                      "validity_days": cq["validity_days"]},
            document_type="quotation",
        )

        await msg_target.reply_document(open(out, "rb"), filename=out.name)
        await msg_target.reply_text(
            f"✅ *Quotation {cq['ref_no']} generated!*\n\nWhat next?",
            reply_markup=post_create_keyboard(),
            parse_mode="Markdown",
        )
    except Exception as exc:
        logger.exception("create_quotation generation failed")
        await msg_target.reply_text(
            friendly_error(exc, "create_quotation"),
            parse_mode="Markdown",
            reply_markup=quotation_confirm_keyboard(),
        )
        return
    finally:
        try:
            await progress.delete()
        except Exception:
            pass

    store.reset(uid)


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > max_len:
            chunks.append(current)
            current = ""
        current += line
    if current:
        chunks.append(current)
    return chunks or [""]


# ── App factory ───────────────────────────────────────────────────────────────

def build_app() -> Application:
    health = get_health()
    logger.info("Startup health: %s", health.summary())

    request = HTTPXRequest(connection_pool_size=8, proxy=None)
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .request(request)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("formats", cmd_formats))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("upgrade", cmd_upgrade))
    app.add_handler(CommandHandler("create", cmd_create))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Global safety net — catches anything that escapes per-handler try/except blocks
    app.add_error_handler(global_error_handler)

    return app
