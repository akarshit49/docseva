#genai: All InlineKeyboard builders for DocSeva bot.
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif"}
_QUOTE_EXTS = {".doc", ".docx", ".pdf"}
_EXCEL_EXTS = {".xls", ".xlsx"}
_PDF_EXPORT_EXTS = {".doc", ".docx", ".xls", ".xlsx"}


def action_keyboard(suffix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    if suffix in _IMAGE_EXTS:
        rows += [
            [InlineKeyboardButton("💧 Add Watermark", callback_data="action:watermark")],
            [InlineKeyboardButton("🖼 Remove Background (PNG)", callback_data="action:bg_remove")],
            [InlineKeyboardButton("📖 Create Product Catalog PDF", callback_data="action:catalog")],
        ]

    if suffix in _QUOTE_EXTS:
        rows += [
            [InlineKeyboardButton("📋 Sister Quotation", callback_data="action:sister")],
            [InlineKeyboardButton("🧮 Validate GST Invoice", callback_data="action:gst_validate")],
            [InlineKeyboardButton("📊 Compare Quotations", callback_data="action:compare_start")],
        ]

    if suffix in {".doc", ".docx"}:
        rows.append([InlineKeyboardButton("🧾 Bill to Make (Invoice PDF)", callback_data="action:bill_to_make")])

    if suffix == ".pdf":
        rows.append([InlineKeyboardButton("📄 Read PDF → Export as DOCX", callback_data="action:to_docx")])

    if suffix in _EXCEL_EXTS:
        rows.append([InlineKeyboardButton("📊 Excel → DOCX (table format)", callback_data="action:to_docx")])

    if suffix in _PDF_EXPORT_EXTS:
        rows.append([InlineKeyboardButton("🖨 Export to PDF", callback_data="action:to_pdf")])

    rows += [
        [InlineKeyboardButton("✏️ Rename File", callback_data="action:rename")],
        [
            InlineKeyboardButton("📁 New File", callback_data="action:new_file"),
            InlineKeyboardButton("❌ Exit", callback_data="action:exit"),
        ],
    ]
    return InlineKeyboardMarkup(rows)



def sister_format_keyboard(formats: list[dict]) -> InlineKeyboardMarkup:
    """Dynamic keyboard listing saved sister-quotation format templates."""
    rows = []
    for fmt in formats:
        rows.append([
            InlineKeyboardButton(
                f"📄 {fmt['name']}",
                callback_data=f"sfmt:{fmt['id']}",
            )
        ])
    rows.append([InlineKeyboardButton("➕ Add New Format", callback_data="sfmt:new")])
    rows.append([
        InlineKeyboardButton("📁 New File", callback_data="action:new_file"),
        InlineKeyboardButton("❌ Exit", callback_data="action:exit"),
    ])
    return InlineKeyboardMarkup(rows)


def sister_manage_keyboard(formats: list[dict]) -> InlineKeyboardMarkup:
    """Keyboard for deleting saved sister-quotation format templates."""
    rows = []
    for fmt in formats:
        rows.append([
            InlineKeyboardButton(
                f"🗑 Delete: {fmt['name']}",
                callback_data=f"sfmt_del:{fmt['id']}",
            )
        ])
    rows.append([InlineKeyboardButton("◀ Back", callback_data="action:new_file")])
    return InlineKeyboardMarkup(rows)


def price_adjust_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("+5%", callback_data="price:+5"),
            InlineKeyboardButton("+10%", callback_data="price:+10"),
            InlineKeyboardButton("+15%", callback_data="price:+15"),
            InlineKeyboardButton("+20%", callback_data="price:+20"),
        ],
        [
            InlineKeyboardButton("-5%", callback_data="price:-5"),
            InlineKeyboardButton("-10%", callback_data="price:-10"),
            InlineKeyboardButton("-15%", callback_data="price:-15"),
            InlineKeyboardButton("-20%", callback_data="price:-20"),
        ],
        [
            InlineKeyboardButton("✏️ Custom %", callback_data="price:custom"),
            InlineKeyboardButton("⏭ Skip", callback_data="action:skip_price"),
        ],
    ])


def comparison_count_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("2", callback_data="cmp_n:2"),
            InlineKeyboardButton("3", callback_data="cmp_n:3"),
            InlineKeyboardButton("4", callback_data="cmp_n:4"),
            InlineKeyboardButton("5", callback_data="cmp_n:5"),
        ],
        [
            InlineKeyboardButton("✏️ Custom (up to 10)", callback_data="cmp_n:custom"),
            InlineKeyboardButton("❌ Cancel", callback_data="action:new_file"),
        ],
    ])


def watermark_mode_keyboard(has_logo: bool = True) -> InlineKeyboardMarkup:
    """KI-13: let the user choose between logo and text watermark."""
    rows = []
    if has_logo:
        rows.append([InlineKeyboardButton("🏢 Use my company logo", callback_data="wm:logo")])
    rows.append([InlineKeyboardButton("🅰 Add custom text watermark", callback_data="wm:text")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="action:new_file")])
    return InlineKeyboardMarkup(rows)


def nav_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📁 New File", callback_data="action:new_file"),
        InlineKeyboardButton("❌ Exit", callback_data="action:exit"),
    ]])


#genai: Main /menu keyboard — surfaces /create so users without a file
#       have a clear entry point alongside profile/history/help.
def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Create from Scratch", callback_data="menu:create")],
        [
            InlineKeyboardButton("⚙️ Settings", callback_data="menu:settings"),
            InlineKeyboardButton("📄 Formats", callback_data="menu:formats"),
        ],
        [
            InlineKeyboardButton("📂 History", callback_data="menu:history"),
            InlineKeyboardButton("❓ Help", callback_data="menu:help"),
        ],
    ])


#genai: WS-3 — entry-point keyboard for /create
def create_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Create Invoice / Bill", callback_data="create:invoice")],
        [InlineKeyboardButton("📋 Create Quotation", callback_data="create:quotation")],
        [InlineKeyboardButton("◀ Back to Menu", callback_data="action:exit")],
    ])


#genai: WS-3 — after items entered, choose to add more / continue / cancel
def items_review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add More Items", callback_data="create:add_more"),
            InlineKeyboardButton("▶️ Continue", callback_data="create:continue"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="create:cancel")],
    ])


#genai: WS-3 — HSN code entry sub-flow keyboard
def hsn_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏭ Skip", callback_data="create:hsn_skip"),
            InlineKeyboardButton("◀ Back", callback_data="create:hsn_back"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="create:cancel")],
    ])


#genai: WS-3 — GST rate quick-pick + custom + per-item
def gst_rate_keyboard() -> InlineKeyboardMarkup:
    """Quick-pick rates apply uniformly to every item. 'Customize per item'
    starts a sub-flow asking for a rate per item."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5%", callback_data="create:gst:5"),
            InlineKeyboardButton("12%", callback_data="create:gst:12"),
            InlineKeyboardButton("18%", callback_data="create:gst:18"),
            InlineKeyboardButton("28%", callback_data="create:gst:28"),
        ],
        [
            InlineKeyboardButton("✏️ Single Custom Rate", callback_data="create:gst:custom"),
            InlineKeyboardButton("0% (No GST)", callback_data="create:gst:0"),
        ],
        [
            InlineKeyboardButton("🎚 Customize per Item", callback_data="create:gst:per_item"),
        ],
        [
            InlineKeyboardButton("◀ Back", callback_data="create:gst_back"),
            InlineKeyboardButton("❌ Cancel", callback_data="create:cancel"),
        ],
    ])


#genai: WS-3 — final confirmation
def invoice_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Generate Invoice PDF", callback_data="create:generate")],
        #genai: KI fix — let the user override the auto-generated invoice number
        [InlineKeyboardButton("✏️ Change Invoice #", callback_data="create:edit_refno")],
        [
            InlineKeyboardButton("◀ Back", callback_data="create:confirm_back"),
            InlineKeyboardButton("❌ Cancel", callback_data="create:cancel"),
        ],
    ])


#genai: WS-3 — quotation confirmation
def quotation_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Generate Quotation DOCX", callback_data="create:generate_q")],
        #genai: KI fix — let the user override the auto-generated ref number
        [InlineKeyboardButton("✏️ Change Ref #", callback_data="create:edit_refno_q")],
        [
            InlineKeyboardButton("◀ Back", callback_data="create:confirm_back"),
            InlineKeyboardButton("❌ Cancel", callback_data="create:cancel"),
        ],
    ])


#genai: WS-3 — after successful generation, suggest workflow chain steps
def post_create_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Create Another", callback_data="create:restart")],
        [
            InlineKeyboardButton("📁 New File", callback_data="action:new_file"),
            InlineKeyboardButton("❌ Exit", callback_data="action:exit"),
        ],
    ])


def profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏢 Update Company Name", callback_data="profile:display_name")],
        [InlineKeyboardButton("📍 Update Address", callback_data="profile:address")],
        [InlineKeyboardButton("📞 Update Phone", callback_data="profile:phone")],
        [InlineKeyboardButton("✉️ Update Email", callback_data="profile:email")],
        [InlineKeyboardButton("🔢 Update GSTIN", callback_data="profile:gstin")],
        [InlineKeyboardButton("🏦 Update Bank Details", callback_data="profile:bank_name")],
        [InlineKeyboardButton("🖼 Upload Logo", callback_data="profile:logo")],
        [InlineKeyboardButton("◀ Back", callback_data="action:new_file")],
    ])
