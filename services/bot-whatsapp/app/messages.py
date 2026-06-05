#genai: Sprint 5 / WS-E — channel-neutral copy. Mirrors Telegram tone.
"""
All user-facing strings live here so the conversation file reads as logic,
not as a wall of copy. Keep these short — WhatsApp UX is brutal about
verbose text and Meta's interactive message body has a 1024-char limit.
"""
from __future__ import annotations

WELCOME_FIRST = (
    "👋 Welcome to DocSeva.\n\n"
    "I turn supplier quotes into your branded customer quotes.\n\n"
    "What's your business name? (e.g. ABC Enterprises)"
)

WELCOME_BACK = (
    "👋 Welcome back, *{company}*.\n\n"
    "📎 Drop your supplier's quote — I'll turn it into your branded "
    "customer quote in seconds."
)

ACK_FILE = "📂 Got *{filename}*.\n\nWhat should I do with it?"

ACK_NON_DOC = (
    "I can only read documents (PDF, DOC, DOCX) or photos of quotes. "
    "Drop one and I'll take it from there."
)

ASK_BUSINESS_NAME_AGAIN = "Please send your business name as plain text (e.g. ABC Enterprises)."

CONFIRM_HEADER = "Here's what I read — please confirm:\n\n*Bill To:* {recipient}\n*Items ({n}):*\n{items}"

CONFIRM_FOOTER = "Reply ✅ to confirm, or ✏️ to edit on the web."

PICK_FORMAT_HEADER = "Pick your output format:"
PICK_FORMAT_DEFAULT_LABEL = "My Default"
PICK_FORMAT_FOOTER = (
    "Tip: you can add saved tender formats from docseva.in/library/formats."
)

GENERATING = "⚙️ Generating your branded quote — one moment…"

DONE = "✅ Done. {used}/{limit} docs used this cycle."

ERROR_GENERIC = "Something went wrong: {message}"

ERROR_QUOTA = (
    "You've used your {limit} docs for this cycle. Upgrade at "
    "docseva.in/billing to keep going."
)

LINK_HELP = (
    "To link this WhatsApp number to an existing DocSeva account, type:\n"
    "`/link <CODE>`\n\n"
    "Get the code from docseva.in/settings/channels."
)

LINK_OK = "🔗 Linked. Welcome to *{company}*."

LINK_FAIL = "That code didn't work: {message}"

WEB_INSTEAD = (
    "This works best on the web — open https://docseva.in/{path} to continue."
)

CANCELLED = "Cancelled. Drop another file whenever you're ready."

UNKNOWN_CMD = (
    "Sorry, I didn't catch that. Drop a supplier quote (PDF/DOC/DOCX) to start, "
    "or type /help."
)

HELP = (
    "📋 *Sister Quotation* — drop a supplier file → get your branded quote.\n"
    "🔗 Link this number to your web account: `/link CODE`\n"
    "🌐 Open the web app: docseva.in"
)


def format_items_block(items: list[dict]) -> str:
    """Compact list of items for the confirm message."""
    lines = []
    for i, it in enumerate(items[:8], start=1):
        desc = (it.get("description") or "—").strip()
        if len(desc) > 60:
            desc = desc[:57] + "…"
        qty = (it.get("qty") or "1").strip()
        unit = it.get("unit_price") or 0
        try:
            unit_str = f"₹{float(unit):,.0f}"
        except (TypeError, ValueError):
            unit_str = "₹—"
        lines.append(f"{i}. {desc} × {qty} @ {unit_str}")
    if len(items) > 8:
        lines.append(f"…and {len(items) - 8} more.")
    return "\n".join(lines) or "(no items detected)"
