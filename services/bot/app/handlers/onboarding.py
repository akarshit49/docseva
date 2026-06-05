#genai: Onboarding conversation handler — registers new users via the API.
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app import api_client
from app.session_store import BotState, SessionStore

logger = logging.getLogger(__name__)

# Shared singleton — bot.py imports this same store instance
store: SessionStore = SessionStore()


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    uid = str(update.effective_user.id)
    session = store.get(uid)

    if session.is_registered:
        profile = session.company_profile
        company = profile.get("display_name") or "your company"
        #genai: WS-D (Sprint 2) — anchor-first welcome. Lead with the headline
        # feature, demote the menu to a secondary hint.
        used = profile.get("docs_used", 0)
        limit = profile.get("docs_limit", 10)
        await update.message.reply_text(
            f"👋 Welcome back, *{company}*!\n\n"
            "📎 *Drop a supplier's quote (PDF / DOC / DOCX) — "
            "I'll turn it into your branded customer quote in seconds.*\n\n"
            f"_Quota: {used}/{limit} docs used this month._\n"
            "Type /tools for utilities, /menu for everything else.",
            parse_mode="Markdown",
        )
        return

    # Check API — maybe user registered in a previous session
    try:
        result = api_client.register_or_login(
            telegram_user_id=uid,
            name=update.effective_user.full_name or "User",
            company_name="My Company",   # placeholder, will be updated
        )
        if not result["is_new"]:
            _populate_session(session, result)
            await update.message.reply_text(
                f"👋 Welcome back to *DocSeva*!\n\n"
                f"📎 *Drop a supplier's quote — I'll turn it into your branded "
                "customer quote in seconds.*\n\n"
                f"📂 *{result['organization']['name']}* · "
                f"{result['organization']['docs_used_this_cycle']}/"
                f"{result['organization']['docs_limit_per_cycle']} docs used\n"
                "Type /tools for utilities, /menu for everything else.",
                parse_mode="Markdown",
            )
            return
    except Exception:
        pass

    # New user — start onboarding
    session.state = BotState.ONBOARDING_NAME
    #genai: WS-D (Sprint 2) — onboarding copy now leads with the anchor promise,
    # not the 12-feature grid. The toolkit is acknowledged but not enumerated.
    await update.message.reply_text(
        "👋 Welcome to *DocSeva*.\n\n"
        "I help dealers, traders, and manufacturers turn *supplier quotes "
        "into your own branded customer quotes in under 2 minutes.*\n\n"
        "Comparison, GST validation, and invoice tools come built-in.\n\n"
        "Let's set up your company in 30 seconds. First — *what's your name?*",
        parse_mode="Markdown",
    )


async def handle_onboarding_text(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, store: SessionStore
) -> bool:
    """
    Handles text input during onboarding states.
    Returns True if it consumed the message, False if not in onboarding.
    """
    uid = str(update.effective_user.id)
    session = store.get(uid)
    text = (update.message.text or "").strip()

    if session.state == BotState.ONBOARDING_NAME:
        session.onboarding_name = text
        session.state = BotState.ONBOARDING_COMPANY
        await update.message.reply_text(
            f"Nice to meet you, *{text}*! 🤝\n\n"
            "What is your *company name*? (e.g. Acme Enterprises)",
            parse_mode="Markdown",
        )
        return True

    if session.state == BotState.ONBOARDING_COMPANY:
        session.onboarding_company = text
        session.state = BotState.ONBOARDING_PHONE
        #genai: WS-11 — improved optional field copy
        await update.message.reply_text(
            f"Great! *{text}* — noted. ✅\n\n"
            "What is your *business phone number*?\n\n"
            "_This is optional — tap /skip if you'd like to add it later._\n"
            "_Your phone won't be shared. It appears on your invoices._",
            parse_mode="Markdown",
        )
        return True

    if session.state == BotState.ONBOARDING_PHONE:
        phone = None if text.lower() == "/skip" else text
        session.state = BotState.ONBOARDING_GSTIN
        session._tmp_phone = phone
        #genai: WS-11 — improved optional field copy
        await update.message.reply_text(
            "What is your *GSTIN*?\n\n"
            "_This is optional — type /skip to add it later from /settings._",
            parse_mode="Markdown",
        )
        return True

    if session.state == BotState.ONBOARDING_GSTIN:
        gstin = None if text.lower() == "/skip" else text.upper()

        # Register user via API
        phone = getattr(session, "_tmp_phone", None)
        uid_str = str(update.effective_user.id)
        try:
            result = api_client.register_or_login(
                telegram_user_id=uid_str,
                name=session.onboarding_name,
                company_name=session.onboarding_company,
                phone=phone,
            )
            _populate_session(session, result)

            # Update profile with GSTIN and phone
            profile_data: dict = {}
            if gstin:
                profile_data["gstin"] = gstin
            if phone:
                profile_data["phone"] = phone
            if profile_data:
                updated = api_client.update_company_profile(uid_str, profile_data)
                session.company_profile.update(updated)

        except Exception as exc:
            logger.error("Registration failed: %s", exc)
            await update.message.reply_text(
                "⚠️ Could not connect to the server. Please try again with /start.",
            )
            session.state = BotState.IDLE
            return True

        await update.message.reply_text(
            f"✅ *You're all set!*\n\n"
            f"🏢 *{session.company_profile.get('display_name', '')}*\n"
            f"📞 {phone or '—'}  |  🔢 {gstin or 'GSTIN not set'}\n\n"
            "You can upload your company logo anytime with /settings\n\n"
            "*Send me a document or image to get started!* 🚀",
            parse_mode="Markdown",
        )
        session.state = BotState.IDLE
        return True

    return False


def _populate_session(session, api_result: dict) -> None:
    session.is_registered = True
    session.user_id = api_result["user"]["id"]
    session.org_id = api_result["organization"]["id"]
    session.company_profile = {
        "display_name": api_result["organization"]["name"],
        "plan": api_result["organization"]["plan"],
        "docs_used": api_result["organization"]["docs_used_this_cycle"],
        "docs_limit": api_result["organization"]["docs_limit_per_cycle"],
    }
    session.state = BotState.IDLE
