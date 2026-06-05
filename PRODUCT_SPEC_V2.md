# DocSeva v2 — Complete Product & Technical Specification

> **Purpose:** This document is the single source of truth for transforming DocSeva from a
> file-conversion tool into an indispensable end-to-end document workflow platform for
> Indian MSMEs. It contains product requirements, conversational UX scripts, technical
> architecture, database changes, API contracts, error handling strategies, and test
> plans — everything a System Architect and Senior Software Engineer need to plan,
> estimate, and implement every feature.
>
> **Audience:** Product Owner, System Architect, Senior Software Engineers, QA
>
> **Last updated:** 31 May 2026

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Assessment](#2-current-state-assessment)
3. [Workstream 1 — Wire Up Output File Storage to MinIO](#3-workstream-1--wire-up-output-file-storage-to-minio)
4. [Workstream 2 — State-Aware Input Handling & Graceful Flow Recovery](#4-workstream-2--state-aware-input-handling--graceful-flow-recovery)
5. [Workstream 3 — Create Invoice / Quotation from Scratch](#5-workstream-3--create-invoice--quotation-from-scratch)
6. [Workstream 4 — Purchase Order (PO) Generator](#6-workstream-4--purchase-order-po-generator)
7. [Workstream 5 — Sister Quotation from Scratch (Default Templates)](#7-workstream-5--sister-quotation-from-scratch-default-templates)
8. [Workstream 6 — Bill from PO or Quotation](#8-workstream-6--bill-from-po-or-quotation)
9. [Workstream 7 — GST Validator on Generated Bills](#9-workstream-7--gst-validator-on-generated-bills)
10. [Workstream 8 — PDF / DOCX In-Place Editing](#10-workstream-8--pdf--docx-in-place-editing)
11. [Workstream 9 — Stop Swallowing Errors + Add Retry](#11-workstream-9--stop-swallowing-errors--add-retry)
12. [Workstream 10 — Progress Indicators for Long Operations](#12-workstream-10--progress-indicators-for-long-operations)
13. [Workstream 11 — UX Polish & Copy Improvements](#13-workstream-11--ux-polish--copy-improvements)
14. [Workstream 12 — Session & File Durability](#14-workstream-12--session--file-durability)
15. [End-to-End Workflow Map](#15-end-to-end-workflow-map)
16. [Database Migration Plan](#16-database-migration-plan)
17. [API Contract Changes](#17-api-contract-changes)
18. [Bot State Machine — Complete Updated Diagram](#18-bot-state-machine--complete-updated-diagram)
19. [Error Code Catalogue](#19-error-code-catalogue)
20. [Testing Strategy](#20-testing-strategy)
21. [Rollout Plan](#21-rollout-plan)
22. [Appendix A — Full Conversational Scripts](#appendix-a--full-conversational-scripts)
23. [Appendix B — Keyboard Definitions](#appendix-b--keyboard-definitions)

---

## 1. Executive Summary

### Vision

DocSeva today is a **point tool** — the user must arrive with a file and leave with a
file. V2 transforms it into an **end-to-end workflow platform**:

```
Create Quotation → Create Sister Quotation → Create PO → Create Bill → Validate GST → Edit Any Document
```

Every step can be entered independently or chained from the previous step's output.
The user never needs to leave the app.

### Key Outcomes

| # | Outcome | Metric |
|---|---------|--------|
| 1 | Users can create documents from scratch (no input file needed) | New "create" flow usage > 30% of total |
| 2 | Every output is stored and re-downloadable | 100% of outputs have `output_file_key` |
| 3 | Users are never confused about what the bot wants | Zero "stuck state" support tickets |
| 4 | Errors are human-readable and recoverable | Session reset only on unrecoverable errors |
| 5 | Full workflow chain (Quote → PO → Bill → GST) available | Chain completion rate tracked |

### Prioritization (Implementation Order)

| Priority | Workstream | Effort | Impact |
|----------|-----------|--------|--------|
| P0 | WS-1: Output file storage | 1 day | Unlocks analytics, re-downloads, audit trail |
| P0 | WS-9: Error handling + retry | 1 day | Prevents silent data loss, improves reliability |
| P0 | WS-2: State-aware input handling | 2 days | Eliminates user confusion, prevents stuck states |
| P0 | WS-10: Progress indicators | 0.5 days | Reduces perceived latency, prevents "is it broken?" |
| P1 | WS-3: Create Invoice from scratch | 3 days | First "create" capability, major value unlock |
| P1 | WS-11: UX polish & copy | 1 day | Professional feel, better onboarding |
| P1 | WS-12: Session & file durability | 1 day | Survives restarts, multi-file flows are safe |
| P2 | WS-5: Sister Quotation from scratch | 2 days | Users without templates can still use the feature |
| P2 | WS-4: PO Generator | 3 days | Natural workflow extension |
| P2 | WS-6: Bill from PO/Quotation | 2 days | Closes the workflow loop |
| P2 | WS-7: GST Validator on generated bills | 0.5 days | Automatic quality check |
| P3 | WS-8: PDF/DOCX editing | 3 days | High UX value but technically complex |

---

## 2. Current State Assessment

### What Exists (Working)

| Component | Status | Notes |
|-----------|--------|-------|
| Telegram bot with state machine | Working | 17 `BotState` values, Redis-backed sessions |
| Sister Quotation (from uploaded file) | Working | User-defined templates (max 10), price adjustment |
| Bill to Make (from uploaded DOC/DOCX) | Working | LLM parsing, HSN prompting, BillTo/ShipTo, PDF render |
| PDF/Excel/DOCX conversions | Working | Pure Python, no LibreOffice |
| Image tools (watermark, bg-remove, catalog) | Working | Logo + text watermark, rembg |
| GST Validator | Working | LLM-based, chunked for long docs |
| Quotation Comparison | Working | 2-10 files, DOCX table output |
| Multi-tenant API | Working | Org/User/Profile/Documents/SisterFormats |
| Onboarding | Working | Name → Company → Phone (skip) → GSTIN (skip) |
| Quota system | Working | Per-org monthly limits by plan |

### What's Broken or Missing

| Issue | Severity | Current Behavior |
|-------|----------|-----------------|
| Outputs not stored in MinIO | High | Files sent via Telegram only; `output_file_key` empty; `/history` shows metadata but no re-download |
| Errors silently swallowed | High | `except Exception: pass` on quota increment and document logging — silent data loss |
| No retry on API calls | High | Single attempt; transient failures cause permanent data loss |
| No state-aware input handling | Medium | User sends text during file-expected state → generic "send a file" message with no context |
| No "go back" in multi-step flows | Medium | Only escape is `/stop` which resets everything |
| No progress indicators | Medium | 10-30 second silence during LLM processing |
| Session reset on every error | Medium | File must be re-uploaded after any failure |
| `format_keyboard()` dead code | Low | Hardcoded Sanmati-era format names still in `keyboards.py` |
| `/upgrade` command referenced but doesn't exist | Low | Dead-end in quota exhaustion message |
| Technical error messages shown to users | Medium | Raw Python exceptions shown: `KeyError: 'items'` |

---

## 3. Workstream 1 — Wire Up Output File Storage to MinIO

### Problem

Output files are sent to the user via Telegram and then lost. The `documents` table has
`output_file_key` but it's never populated. The `upload_output()` function exists in
`storage_client.py` but is never called. The `docseva-outputs` MinIO bucket sits empty.

### Requirements

1. After every successful document processing, upload the output file to MinIO before sending to the user.
2. Store the returned MinIO key in `documents.output_file_key` via the `log_document` API call.
3. Also upload and store input files in `docseva-uploads` for future analytics.
4. Make `/history` show a re-download option for documents that have an `output_file_key`.
5. Add a cleanup job that deletes expired files (based on `documents.expires_at`).

### Technical Design

#### 3.1 Storage Key Format

```
# Outputs
outputs/{org_id}/{document_id}/{filename}

# Inputs (new)
uploads/{org_id}/{document_id}/{original_filename}
```

Using `document_id` ensures uniqueness even if filenames collide.

#### 3.2 Changes to `storage_client.py`

```python
# Current — unused but correct pattern
def upload_output(org_id: str, local_path: Path) -> str:
    key = f"{org_id}/outputs/{local_path.name}"
    ...

# New — add doc_id for uniqueness, add upload_input
def upload_output(org_id: str, doc_id: str, local_path: Path) -> str:
    key = f"outputs/{org_id}/{doc_id}/{local_path.name}"
    with open(local_path, "rb") as fh:
        _client().put_object(
            Bucket=settings.minio_bucket_outputs,
            Key=key,
            Body=fh.read(),
        )
    return key

def upload_input(org_id: str, doc_id: str, local_path: Path) -> str:
    key = f"uploads/{org_id}/{doc_id}/{local_path.name}"
    with open(local_path, "rb") as fh:
        _client().put_object(
            Bucket=settings.minio_bucket_uploads,
            Key=key,
            Body=fh.read(),
        )
    return key
```

#### 3.3 Changes to `bot.py` — Upload Pattern

Every processing function follows this updated pattern:

```python
# BEFORE (current):
try:
    api_client.increment_quota(uid)
    api_client.log_document(uid, "sister_quotation", session.original_filename, out.name)
except Exception:
    pass

# AFTER (new):
output_file_key = await _upload_output_file(uid, session, out)
await _log_and_increment(uid, "sister_quotation", session.original_filename, out.name, output_file_key)
```

New helper functions in `bot.py`:

```python
async def _upload_output_file(uid: str, session, output_path: Path) -> str | None:
    """Upload output to MinIO. Returns file key or None on failure."""
    org_id = session.org_id
    if not org_id:
        return None
    try:
        from app.storage_client import upload_output
        import uuid
        doc_id = str(uuid.uuid4())
        key = await asyncio.get_event_loop().run_in_executor(
            None, lambda: upload_output(org_id, doc_id, output_path)
        )
        return key
    except Exception:
        logger.warning("Failed to upload output to MinIO for user %s", uid, exc_info=True)
        return None

async def _log_and_increment(
    uid: str, feature: str, original_filename: str,
    output_filename: str, output_file_key: str | None,
    metadata: dict | None = None,
) -> None:
    """Increment quota and log document with retry. Never throws."""
    for attempt in range(3):
        try:
            api_client.increment_quota(uid)
            api_client.log_document(
                uid, feature, original_filename, output_filename,
                output_file_key=output_file_key,
                metadata=metadata,
            )
            return
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                logger.error(
                    "Failed to log document after 3 attempts: user=%s feature=%s",
                    uid, feature, exc_info=True,
                )
```

#### 3.4 Changes to `/history` Command

```python
async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    # ... existing code to fetch docs ...

    lines = ["📂 *Recent Documents*\n"]
    for d in docs[:10]:
        status = "✅" if d.get("status") == "completed" else "❌"
        when = format_history_date(d.get("created_at", ""))
        download = ""
        if d.get("download_url"):
            download = f" — [Download]({d['download_url']})"
        lines.append(
            f"{status} `{d.get('output_filename') or d.get('original_filename', '?')}` — "
            f"{d.get('feature', '')} — {when}{download}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown",
                                     disable_web_page_preview=True)
```

#### 3.5 File Cleanup Job

Add a periodic cleanup task. For MVP, run as a management command or cron:

```python
# services/api/app/tasks/cleanup.py
async def cleanup_expired_documents():
    """Delete MinIO objects for expired documents and mark them cleaned."""
    expired = await db.execute(
        select(Document).where(
            Document.expires_at < func.now(),
            Document.output_file_key.isnot(None),
        )
    )
    for doc in expired.scalars():
        try:
            delete_object(settings.minio_bucket_outputs, doc.output_file_key)
        except Exception:
            pass
        doc.output_file_key = None
    await db.commit()
```

#### 3.6 Storage Cost Estimate

| Scale | Docs/month | Avg size | Monthly storage | Monthly cost (S3) |
|-------|-----------|----------|----------------|-------------------|
| MVP | 1,000 | 500 KB | 500 MB | ~$0.01 |
| Growth | 10,000 | 500 KB | 5 GB | ~$0.12 |
| Scale | 100,000 | 500 KB | 50 GB | ~$1.15 |

Storage cost is negligible. The analytics and re-download value far exceeds the cost.

---

## 4. Workstream 2 — State-Aware Input Handling & Graceful Flow Recovery

### Problem

When a user sends unexpected input (text instead of file, file instead of text, random
question during a multi-step flow), the bot either ignores it, shows a generic "send a
file" message, or silently proceeds with wrong data. The user has no idea what the bot
expects, and no way to recover except `/stop` which resets everything.

### Design Principles

1. **Every state must have a specific "expected input" definition.**
2. **When unexpected input arrives, tell the user exactly what's expected.**
3. **Always offer an escape: `/stop` to cancel, or a Cancel button.**
4. **Never reset the session on recoverable errors — preserve the uploaded file.**
5. **If user sends a new file mid-flow, ask if they want to switch.**

### 4.1 State Input Expectations Map

| BotState | Expected Input | On Wrong Input |
|----------|---------------|---------------|
| `IDLE` | File or command | "Send a file to get started, or /menu for options." |
| `WAITING_ACTION` | Callback button tap | "Please tap one of the buttons above, or send /stop to cancel." |
| `WAITING_FORMAT` | Callback button tap | "Please select a format from the buttons above." |
| `WAITING_PRICE_ADJUST` | Callback button tap | "Tap a price adjustment button, or tap Skip to proceed." |
| `WAITING_PRICE_CUSTOM` | Number (text) | "Please enter a number like `10` or `-5`. Type /stop to cancel." |
| `WAITING_RENAME` | Text (new filename) | "Please type the new filename. Type /stop to cancel." |
| `WAITING_BILL_META` | Text: `BILL_NO, DATE` | "Please enter bill number and date: `INV-001, 31-05-2024`. Type /stop to cancel." |
| `WAITING_BILL_HSN` | Text: `1: 8481` or `skip` | "Enter HSN codes (e.g. `1: 8481`) or type `skip`. Type /stop to cancel." |
| `WAITING_BILL_TO_DETAILS` | Text: multi-line BillTo | "Please provide BillTo details (Name, Address). Type /stop to cancel." |
| `WAITING_CATALOG_DETAILS` | Text: `Name \| Desc \| Price` | "Enter item details: `Name \| Description \| Price`. Type /stop to cancel." |
| `WAITING_COMPARISON_COUNT` | Callback button | "Please select how many quotations to compare." |
| `WAITING_COMPARISON_CUSTOM_COUNT` | Number 2-10 | "Enter a number between 2 and 10. Type /stop to cancel." |
| `WAITING_COMPARISON_FILES` | Document file | "I need quotation file {n}/{total}. Please send a document (DOC/DOCX/PDF/Excel)." |
| `WAITING_WATERMARK_MODE` | Callback button | "Please choose a watermark mode from the buttons." |
| `WAITING_WATERMARK_TEXT` | Text | "Enter the watermark text (max 80 chars). Type /stop to cancel." |
| `WAITING_SISTER_FORMAT_FILE` | Document file | "I need a format template file (PDF/DOC/DOCX). Send /stop to cancel." |
| `WAITING_SISTER_FORMAT_NAME` | Text (1-60 chars) | "Enter a name for this format (1-60 characters). Type /stop to cancel." |
| `UPDATING_PROFILE_FIELD` | Text (or photo for logo) | "Enter the new value for {field}. Type /stop to cancel." |
| `CREATING_INVOICE_*` | (varies by sub-state) | (see WS-3 section) |

### 4.2 Implementation — Enhanced `handle_text` Fallback

Replace the generic fallback at the end of `handle_text` with a state-aware router:

```python
# At the bottom of handle_text, REPLACE the generic fallback with:

state_hints = {
    BotState.WAITING_ACTION: (
        "I'm waiting for you to choose an action.\n"
        "Tap one of the buttons on the message above, or send /stop to cancel."
    ),
    BotState.WAITING_COMPARISON_FILES: None,  # special handler below
    BotState.WAITING_SISTER_FORMAT_FILE: (
        "I'm waiting for a format template file (PDF, DOC, or DOCX).\n"
        "Please send the file as a document, or type /stop to cancel."
    ),
    BotState.WAITING_FORMAT: (
        "Please select a format from the buttons above, or type /stop to cancel."
    ),
    BotState.WAITING_PRICE_ADJUST: (
        "Would you like to adjust prices? Tap a button above, or tap *Skip* to proceed.",
    ),
    BotState.WAITING_WATERMARK_MODE: (
        "Please choose a watermark mode from the buttons above."
    ),
    BotState.WAITING_COMPARISON_COUNT: (
        "Please select how many quotations to compare from the buttons above."
    ),
}

if session.state in state_hints:
    hint = state_hints[session.state]
    if hint is None and session.state == BotState.WAITING_COMPARISON_FILES:
        collected = len(session.comparison_files)
        total = session.comparison_total
        hint = (
            f"I'm waiting for quotation {collected + 1} of {total}.\n"
            f"Please send a document file (DOC, DOCX, PDF, or Excel), "
            f"or type /stop to cancel the comparison."
        )
    await update.message.reply_text(hint, parse_mode="Markdown")
    return

# If truly in IDLE with no context:
await update.message.reply_text(
    "📎 Send me a file (DOC, DOCX, PDF, Excel, or image) to get started, "
    "or type /menu to see all options.",
)
```

### 4.3 Implementation — File Sent During Text-Expected State

Add to `handle_document`, after the comparison/sister-format checks but before the
general file download:

```python
# States where we expect TEXT, not a file
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
}

if session.state in _TEXT_EXPECTED_STATES:
    await update.message.reply_text(
        f"⚠️ I'm expecting a text response right now, not a file.\n\n"
        f"Send /stop to cancel the current action and start fresh with this file.",
    )
    return
```

### 4.4 Implementation — New File During Active Flow (Flow Interruption)

When a user sends a new file while already in a file-based flow (e.g., already has a
pending file in `WAITING_ACTION`), ask them what they want to do:

```python
# New BotState
CONFIRMING_FILE_REPLACE = "confirming_file_replace"

# In handle_document, when session already has a pending_file:
if session.state == BotState.WAITING_ACTION and session.pending_file:
    # Store the new file temporarily
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
```

### 4.5 Implementation — Gentle Session Reset (Preserve File)

Create a new helper that resets action state but keeps the file:

```python
def soft_reset(self, user_id: str) -> UserSession:
    """Reset flow state but keep file and registration. User can try another action."""
    session = self._sessions.get(user_id)
    if not session:
        return UserSession()
    session.state = BotState.WAITING_ACTION if session.pending_file else BotState.IDLE
    session.pending_bill_data = None
    session.pending_quote_data = None
    session.pending_quote_format = None
    session.pending_quote_stem = ""
    session.comparison_total = 0
    session.comparison_files = []
    session.updating_field = ""
    session.pending_watermark_mode = ""
    self._persist(user_id, session)
    return session
```

Use `soft_reset` instead of `reset` on recoverable errors:

```python
# BEFORE:
except Exception as exc:
    logger.exception("sister quotation failed")
    await query.edit_message_text(f"❌ Conversion failed: {exc}")
    store.reset(uid)  # ← user loses their file

# AFTER:
except Exception as exc:
    logger.exception("sister quotation failed")
    friendly_msg = _friendly_error(exc, "sister_quotation")
    session = store.soft_reset(uid)  # ← file preserved
    if session.pending_file:
        await query.edit_message_text(
            f"{friendly_msg}\n\n"
            "Your file is still loaded — tap an action to try again:",
            reply_markup=action_keyboard(session.pending_file.suffix.lower()),
        )
    else:
        await query.edit_message_text(friendly_msg)
```

### 4.6 Implementation — "Go Back" Button in Multi-Step Flows

Add a ◀ Back button to every step of multi-step flows:

```python
# Bill to Make — after bill meta is entered and HSN is prompted:
# Add to the HSN prompt message:
reply_markup=InlineKeyboardMarkup([
    [InlineKeyboardButton("⏭ Skip HSN codes", callback_data="bill:skip_hsn")],
    [InlineKeyboardButton("◀ Back to actions", callback_data="action:back_to_actions")],
    [InlineKeyboardButton("❌ Cancel", callback_data="action:new_file")],
])
```

Callback handler for `action:back_to_actions`:

```python
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
```

---

## 5. Workstream 3 — Create Invoice / Quotation from Scratch

### Problem

Today, users must upload a DOC/DOCX file to create a Bill/Invoice. Many MSMEs don't
have digital files — they have handwritten notes or verbal agreements. They need to
create invoices from scratch inside the app.

### User Story

> As a small business owner, I want to create a professional GST invoice by just
> answering a few questions, without needing to upload any file.

### 5.1 New Bot States

```python
# Add to BotState enum:
CREATING_INVOICE_BILLTO = "creating_invoice_billto"
CREATING_INVOICE_ITEMS = "creating_invoice_items"
CREATING_INVOICE_MORE_ITEMS = "creating_invoice_more_items"
CREATING_INVOICE_HSN = "creating_invoice_hsn"
CREATING_INVOICE_GST_TYPE = "creating_invoice_gst_type"
CREATING_INVOICE_CONFIRM = "creating_invoice_confirm"
```

### 5.2 New Menu Entry Point

Add to the main menu and as a command:

```python
# New command: /create
async def cmd_create(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_auth(update):
        return
    await update.message.reply_text(
        "✨ *Create a New Document*\n\n"
        "What would you like to create?",
        reply_markup=create_menu_keyboard(),
        parse_mode="Markdown",
    )

# New keyboard:
def create_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Create Invoice / Bill", callback_data="create:invoice")],
        [InlineKeyboardButton("📋 Create Quotation", callback_data="create:quotation")],
        [InlineKeyboardButton("📦 Create Purchase Order", callback_data="create:po")],
        [InlineKeyboardButton("◀ Back to Menu", callback_data="action:exit")],
    ])
```

### 5.3 Complete Conversational Flow — Create Invoice

```
USER taps: 🧾 Create Invoice / Bill
BOT:  🧾 *Create Invoice*

      I'll walk you through it step by step.
      Your company details will be auto-filled from your profile.

      *Step 1/5 — Bill To (Customer)*

      Who is this invoice for? Send the customer details:
      `Name: Customer Company Name`
      `Address: Full postal address`
      `GSTIN: GSTIN or NA`
      `State: State name`

      (Type /stop to cancel anytime)
───────────────────────────────────────
USER: Name: Roorkee Scientific
      Address: 12 Civil Lines, Roorkee
      GSTIN: 05AABCR1234A1Z5
      State: Uttarakhand
───────────────────────────────────────
BOT:  ✅ *Customer:* Roorkee Scientific
      📍 12 Civil Lines, Roorkee
      🔢 GSTIN: 05AABCR1234A1Z5

      *Step 2/5 — Add Items*

      Send items one per line in this format:
      `Item Name | Qty | Unit Price | HSN Code (optional)`

      Example:
      `Digital Thermometer | 2 | 4500 | 9025`
      `pH Meter | 1 | 12000 | 9027`
      `Calibration Service | 1 | 2000`

      Send all items at once, or add them one by one.
───────────────────────────────────────
USER: Digital Thermometer | 2 | 4500 | 9025
      pH Meter | 1 | 12000 | 9027
      Calibration Service | 1 | 2000
───────────────────────────────────────
BOT:  ✅ *3 items added:*

      │ # │ Item                  │ Qty │ Price   │ HSN  │
      │ 1 │ Digital Thermometer   │  2  │ ₹4,500  │ 9025 │
      │ 2 │ pH Meter              │  1  │ ₹12,000 │ 9027 │
      │ 3 │ Calibration Service   │  1  │ ₹2,000  │      │

      [➕ Add More Items]  [✏️ Edit Items]  [▶️ Continue]
───────────────────────────────────────
USER taps: ▶️ Continue
───────────────────────────────────────
BOT:  *Step 3/5 — HSN / SAC Codes*

      ⚠️ Item 3 (Calibration Service) is missing an HSN/SAC code.

      Enter the code:
      `3: 998719`

      Or tap Skip to leave it blank.

      [⏭ Skip]  [◀ Back]
───────────────────────────────────────
USER: 3: 998719
───────────────────────────────────────
BOT:  ✅ All items have HSN/SAC codes.

      *Step 4/5 — GST Rate*

      Select the GST rate for this invoice:

      [5%]  [12%]  [18%]  [28%]
      [✏️ Custom Rate]  [🔀 Per-Item Rate]
───────────────────────────────────────
USER taps: 18%
───────────────────────────────────────
BOT:  *Step 5/5 — Review & Generate*

      🧾 *Invoice Summary*
      ━━━━━━━━━━━━━━━━━━━━━━
      📋 Invoice #: SV-0042 (auto)
      📅 Date: 31-05-2026

      👤 *Bill To:* Roorkee Scientific
      📍 12 Civil Lines, Roorkee
      🔢 GSTIN: 05AABCR1234A1Z5

      📦 *Items:* 3 items
      💰 Subtotal: ₹23,000.00
      🏛 IGST @18%: ₹4,140.00
      ━━━━━━━━━━━━━━━━━━━━━━
      💵 *Total: ₹27,140.00*

      *(Twenty Seven Thousand One Hundred Forty Only)*

      [✅ Generate Invoice PDF]  [✏️ Edit]  [❌ Cancel]
───────────────────────────────────────
USER taps: ✅ Generate Invoice PDF
───────────────────────────────────────
BOT:  ⏳ Generating invoice PDF... (step 1/2)
BOT:  ⚙️ Applying company branding... (step 2/2)
BOT:  [📄 SV-0042_invoice.pdf]

      ✅ *Invoice SV-0042 generated!*

      What would you like to do next?

      [📦 Create PO from this Invoice]
      [📋 Create Sister Quotation]
      [✅ Validate GST]
      [📁 New File]  [❌ Exit]
```

### 5.4 Technical Implementation

#### New Session Fields

```python
# Add to UserSession dataclass:
@dataclass
class CreateInvoiceData:
    bill_to: dict = field(default_factory=dict)
    ship_to: dict = field(default_factory=dict)
    items: list = field(default_factory=list)
    gst_rate: float = 18.0
    per_item_gst: bool = False
    bill_number: str = ""
    bill_date: str = ""

# Add to UserSession:
pending_create_invoice: CreateInvoiceData | None = None
```

#### Item Parsing Function

```python
def parse_invoice_items(text: str) -> list[dict]:
    """Parse user-entered items in 'Name | Qty | Price | HSN' format."""
    items = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        item = {
            "name": parts[0],
            "qty": _parse_number(parts[1], default=1),
            "unit_cost": _parse_number(parts[2], default=0),
            "hsn": parts[3] if len(parts) > 3 else "",
        }
        item["amount"] = round(item["qty"] * item["unit_cost"], 2)
        items.append(item)
    return items

def _parse_number(s: str, default: float = 0) -> float:
    """Parse a number, stripping currency symbols and commas."""
    s = s.replace("₹", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return default
```

#### Auto-Generated Invoice Number

```python
async def _next_invoice_number(uid: str) -> str:
    """Get next invoice number from profile's invoice_prefix + counter."""
    profile = await _refresh_profile(uid)
    prefix = profile.get("invoice_prefix", "INV")
    counter = profile.get("invoice_counter", 1)
    return f"{prefix}-{counter:04d}"

# After successful generation, increment the counter:
api_client.update_company_profile(uid, {
    "invoice_counter": current_counter + 1
})
```

#### PDF Generation — Reuse Existing `bill_to_make.py`

The existing `generate_bill_pdf` function already accepts structured data. The
"create from scratch" flow constructs the same data format without LLM parsing:

```python
async def _generate_scratch_invoice(update, uid, session):
    data = session.pending_create_invoice
    parsed = {
        "bill_to": data.bill_to,
        "ship_to": data.ship_to or data.bill_to,
        "items": [],
        "gst_rate": data.gst_rate,
    }
    for i, item in enumerate(data.items, 1):
        parsed["items"].append({
            "sno": str(i),
            "name": item["name"],
            "hsn": item.get("hsn", ""),
            "unit_cost": item["unit_cost"],
            "amount": item["amount"],
            "gst_rate": item.get("gst_rate", data.gst_rate),
        })
    parsed = _normalize_bill_data(parsed)  # reuse existing normalizer

    # Generate PDF using existing renderer
    profile = session.company_profile
    company_info = _build_company_info(profile or {})
    logo_local = await _download_user_logo(uid, session)
    out = _user_tmp(uid, f"{data.bill_number}_invoice.pdf")
    await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: generate_bill_pdf(parsed, data.bill_number, data.bill_date,
                                   out, company_info, logo_path=logo_local)
    )
    return out, parsed
```

### 5.5 Create Quotation from Scratch — Similar Flow

Same flow as invoice but with different output format (DOCX quotation instead of
PDF invoice) and different fields:

- No GST breakdown needed (optional)
- Add: Validity period, Payment terms, Delivery terms
- Output: DOCX using the sister quotation renderer

```
Create Quotation Flow:
1. Customer details (same as invoice BillTo)
2. Items (Name | Qty | Price — no HSN needed)
3. Terms: validity (days), payment terms, delivery terms (all optional, with defaults)
4. Review & Generate
5. Output: DOCX quotation with company branding
```

---

## 6. Workstream 4 — Purchase Order (PO) Generator

### Problem

After receiving/creating a quotation, the natural next step is generating a Purchase
Order. Today users do this manually in Word. DocSeva should automate this.

### Entry Points

1. **From existing quotation:** User uploads a quotation file → action menu shows "📦 Create PO"
2. **From scratch:** User taps "📦 Create Purchase Order" in the create menu → guided flow
3. **Chained from sister quotation output:** After generating a sister quotation, offer "Create PO from this"

### 6.1 New Bot States

```python
CREATING_PO_VENDOR = "creating_po_vendor"
CREATING_PO_ITEMS = "creating_po_items"
CREATING_PO_TERMS = "creating_po_terms"
CREATING_PO_CONFIRM = "creating_po_confirm"
```

### 6.2 PO Data Structure

```python
@dataclass
class PurchaseOrderData:
    po_number: str = ""
    po_date: str = ""
    vendor: dict = field(default_factory=dict)    # name, address, gstin
    delivery_to: dict = field(default_factory=dict)  # defaults to company address
    items: list = field(default_factory=list)
    delivery_terms: str = "Ex-Works"
    payment_terms: str = "30 days from invoice date"
    validity_days: int = 30
    notes: str = ""
    source_quotation_ref: str = ""  # reference to quotation number if chained
```

### 6.3 Conversational Flow — PO from Uploaded Quotation

```
USER uploads: competitor_quote.pdf
BOT:  📂 *competitor_quote.pdf* received.
      What would you like to do?
      [...existing buttons...]
      [📦 Generate Purchase Order]    ← NEW button
      [📁 New File]  [❌ Exit]
───────────────────────────────────────
USER taps: 📦 Generate Purchase Order
───────────────────────────────────────
BOT:  ⏳ Reading quotation...
BOT:  📦 *Create Purchase Order*

      I've extracted the following from the quotation:

      📋 *Vendor:* XYZ Instruments
      📦 *Items:* 5 items, Total: ₹1,45,000

      │ # │ Item               │ Qty │ Price    │
      │ 1 │ Microscope BX-53   │  2  │ ₹45,000  │
      │ 2 │ Slides (box/100)   │ 10  │ ₹500     │
      │ ...                                      │

      Is this correct?

      [✅ Looks Good, Continue]  [✏️ Edit Items]  [❌ Cancel]
───────────────────────────────────────
USER taps: ✅ Looks Good, Continue
───────────────────────────────────────
BOT:  *Delivery & Payment Terms*

      Select or customize:
      📍 Deliver to: (your company address from profile)

      [🚚 Ex-Works]  [🏭 FOR Destination]  [✏️ Custom]

      💳 Payment: 30 days from invoice

      [✅ Use defaults]  [✏️ Customize terms]
───────────────────────────────────────
USER taps: ✅ Use defaults
───────────────────────────────────────
BOT:  📦 *PO Summary*
      ━━━━━━━━━━━━━━━━
      PO #: PO-0015 (auto)
      Date: 31-05-2026
      Vendor: XYZ Instruments
      Items: 5, Total: ₹1,45,000
      Delivery: Ex-Works
      Payment: 30 days

      [✅ Generate PO PDF]  [✏️ Edit]  [❌ Cancel]
───────────────────────────────────────
USER taps: ✅ Generate PO PDF
───────────────────────────────────────
BOT:  [📄 PO-0015.pdf]
      ✅ *Purchase Order PO-0015 generated!*

      [🧾 Create Invoice from this PO]
      [📁 New File]  [❌ Exit]
```

### 6.4 Database Changes

```python
# Add to CompanyProfile model:
po_prefix: Mapped[str] = mapped_column(Text, default="PO")
po_counter: Mapped[int] = mapped_column(Integer, default=1)
```

### 6.5 PO PDF Renderer

Create `services/bot/app/processors/po_generator.py`:

- Layout: Company header (same as invoice), PO number + date, Vendor details,
  Items table (S.No, Description, HSN, Qty, Unit Price, Amount), Terms section,
  Authorized signatory
- Reuse `_InvoicePDF` base class, `_draw_header`, `_cell`, `_s` helpers from `bill_to_make.py`

### 6.6 LLM Extraction for PO from Quotation

Create a prompt similar to `_SYSTEM_PROMPT` in `bill_to_make.py` but for quotation parsing:

```python
_PO_EXTRACT_PROMPT = """\
You are a document data extractor. Extract vendor and item data from this quotation.
Return ONLY valid JSON:
{
  "vendor": {"name": "...", "address": "...", "gstin": "..."},
  "quotation_ref": "quotation number if present",
  "items": [
    {"name": "...", "qty": 1, "unit_cost": 0.0, "amount": 0.0, "hsn": ""}
  ]
}
...(rules similar to bill extraction)...
"""
```

---

## 7. Workstream 5 — Sister Quotation from Scratch (Default Templates)

### Problem

If a user doesn't have their own quotation format template and doesn't have a competitor's
quotation to convert, they can't use the Sister Quotation feature at all. We should let them
create a quotation from scratch using built-in templates.

### 7.1 Built-In Template Gallery

Offer 3 pre-designed templates that are bundled with the bot:

| Template | Style | Best For |
|----------|-------|---------|
| Professional | Clean, modern, company header + footer, bordered table | Engineering/IT services |
| Compact | Dense, more items per page, minimal styling | Trading/wholesale |
| Government | Formal, serial-numbered, terms & conditions block | Government tenders |

### 7.2 Template Files

Store 3 DOCX template files in `assets/templates/`:
```
assets/templates/
├── quotation_professional.docx
├── quotation_compact.docx
└── quotation_government.docx
```

These are `docxtpl` (Jinja2) templates with placeholders:
```
{{ company_name }}
{{ company_address }}
{{ company_gstin }}
{{ customer_name }}
{{ customer_address }}
{{ date }}
{{ quotation_number }}
{% for item in items %}
{{ item.sno }} | {{ item.name }} | {{ item.qty }} | {{ item.rate }} | {{ item.amount }}
{% endfor %}
{{ total }}
{{ terms }}
```

### 7.3 Flow

```
USER taps: 📋 Create Quotation (from /create menu, no file uploaded)
───────────────────────────────────────
BOT:  📋 *Create Quotation from Scratch*

      Choose a template style:

      [📐 Professional — clean & modern]
      [📊 Compact — dense, more items]
      [🏛 Government — formal tender style]

      Or upload your own template:
      [📤 Use my own template]
───────────────────────────────────────
USER taps: 📐 Professional
───────────────────────────────────────
BOT:  Great choice! Now let's fill in the details.

      *Step 1 — Customer Details*
      (Same as invoice BillTo flow...)
───────────────────────────────────────
      ... (same item entry flow as Create Invoice) ...
───────────────────────────────────────
BOT:  *Terms & Conditions (optional)*

      Enter any terms, or tap Skip for defaults:
      • Validity: 30 days
      • Payment: 100% advance
      • Delivery: 2-3 weeks from PO

      [⏭ Use Defaults]  [✏️ Custom Terms]
───────────────────────────────────────
      ... (review & generate) ...
───────────────────────────────────────
BOT:  [📄 QT-0008_quotation.docx]

      ✅ Quotation QT-0008 generated!

      [📋 Create Sister Quotation from this]
      [📦 Create PO from this]
      [📁 New File]  [❌ Exit]
```

### 7.4 Database Changes

```python
# Add to CompanyProfile model:
quotation_prefix: Mapped[str] = mapped_column(Text, default="QT")
quotation_counter: Mapped[int] = mapped_column(Integer, default=1)
```

---

## 8. Workstream 6 — Bill from PO or Quotation

### Problem

After a PO is approved, the next step is creating an invoice/bill. Users currently
re-enter all data manually. We should allow creating a bill directly from a PO or
approved quotation.

### 8.1 Entry Points

1. **Chained from PO generation:** "Create Invoice from this PO" button
2. **From uploaded PO file:** Action menu shows "🧾 Create Invoice from this PO"
3. **From saved document history:** Re-use previously extracted data

### 8.2 Implementation

This is the simplest workstream because the data is already structured. When chaining
from a PO or quotation, the extracted data is passed directly to the Bill-to-Make
renderer:

```python
async def _create_bill_from_structured_data(update, uid, session, source_data, source_type):
    """Create a bill/invoice from pre-structured data (PO or quotation)."""
    # Auto-generate bill number
    bill_number = await _next_invoice_number(uid)
    bill_date = datetime.now().strftime("%d-%m-%Y")

    # Map source data to bill format
    parsed = {
        "bill_to": source_data.get("vendor") or source_data.get("bill_to", {}),
        "ship_to": source_data.get("delivery_to") or source_data.get("ship_to", {}),
        "items": source_data.get("items", []),
        "gst_rate": source_data.get("gst_rate", 18),
    }

    # If source is PO, swap vendor → bill_to (the vendor is billing the PO issuer)
    if source_type == "po":
        # Bill from the PO issuer's perspective: vendor bills the company
        parsed["bill_to"] = source_data.get("delivery_to", {})
        parsed["ship_to"] = source_data.get("delivery_to", {})

    # Allow user to confirm/edit before generating
    session.pending_bill_data = {
        "parsed": parsed,
        "bill_no": bill_number,
        "bill_date": bill_date,
    }
    session.state = BotState.CREATING_INVOICE_CONFIRM

    # Show summary for confirmation
    await _show_invoice_summary(update, session, bill_number, bill_date, parsed)
```

### 8.3 The Complete Workflow Chain

```
Quotation (created or uploaded)
    ↓ "Create Sister Quotation"
Sister Quotation (reformatted in your style)
    ↓ "Create PO from this"
Purchase Order (formal PO document)
    ↓ "Create Invoice from this PO"
Invoice/Bill (GST invoice PDF)
    ↓ "Validate GST"
GST Validation Report (errors/OK)
    ↓ "Edit" (if errors found)
Corrected Invoice
```

Each step auto-populates from the previous step's structured data. The user only
needs to confirm and optionally edit. This is the killer workflow.

---

## 9. Workstream 7 — GST Validator on Generated Bills

### Problem

Currently GST validation only works on uploaded files. After we generate an invoice,
we should offer automatic GST validation as a follow-up action.

### 9.1 Implementation

After generating any invoice (from scratch or from file), add a "Validate GST" option.
Since we have the structured data, we can validate without LLM:

```python
def validate_invoice_data(parsed: dict, company_profile: dict) -> list[str]:
    """Validate structured invoice data. Returns list of issues (empty = valid)."""
    issues = []
    items = parsed.get("items", [])

    # Check: all items have amounts > 0
    for i, item in enumerate(items, 1):
        if float(item.get("amount", 0)) <= 0:
            issues.append(f"Item {i} ({item.get('name', '?')}) has zero amount")

    # Check: GST rate is valid (0, 5, 12, 18, 28)
    valid_rates = {0, 5, 12, 18, 28}
    for i, item in enumerate(items, 1):
        rate = float(item.get("gst_rate", 0))
        if rate not in valid_rates:
            issues.append(f"Item {i}: GST rate {rate}% is non-standard")

    # Check: GSTIN format (if provided)
    bill_to = parsed.get("bill_to", {})
    gstin = bill_to.get("gstin", "")
    if gstin and gstin != "NA":
        import re
        if not re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\d[Z][A-Z\d]$", gstin):
            issues.append(f"Bill To GSTIN '{gstin}' format appears invalid")

    # Check: HSN codes present
    missing_hsn = [i for i, item in enumerate(items, 1) if not item.get("hsn")]
    if missing_hsn:
        issues.append(f"Items {missing_hsn} are missing HSN/SAC codes")

    # Check: inter-state vs intra-state GST
    company_state = company_profile.get("state", "").lower()
    bill_state = bill_to.get("state_name", "").lower()
    if company_state and bill_state:
        is_inter = company_state != bill_state
        # Future: check IGST vs CGST+SGST based on inter/intra

    # Check: math — subtotal + GST = total
    subtotal = float(parsed.get("subtotal", 0))
    gst_amount = float(parsed.get("gst_amount", 0))
    total = float(parsed.get("total", 0))
    expected_total = round(subtotal + gst_amount, 2)
    if abs(total - expected_total) > 0.01:
        issues.append(f"Total mismatch: {total} ≠ {subtotal} + {gst_amount} = {expected_total}")

    return issues
```

### 9.2 Auto-Validate After Generation

```python
# After generating any invoice:
issues = validate_invoice_data(parsed, session.company_profile)
if issues:
    issue_text = "\n".join(f"⚠️ {i}" for i in issues)
    await update.message.reply_text(
        f"🧮 *Auto GST Check* found {len(issues)} issue(s):\n\n{issue_text}\n\n"
        "You can edit the invoice to fix these.",
        parse_mode="Markdown",
    )
```

---

## 10. Workstream 8 — PDF / DOCX In-Place Editing

### Problem

After generating a document, users often need small corrections — a wrong name, address,
HSN code, or amount. Currently they must start over from scratch. We need a lightweight
edit capability.

### 10.1 Scope & Constraints

**What we CAN edit (MVP):**
- Documents that DocSeva generated (we have the structured data in `documents.metadata`)
- Text fields: names, addresses, GSTIN, item names, amounts, dates, HSN codes
- Re-render the document from edited structured data

**What we CANNOT edit (out of scope):**
- Arbitrary PDFs uploaded by users (PDF editing is extremely hard)
- Layout/styling changes
- Image editing within documents

### 10.2 Key Technical Decision — Store Structured Data in Metadata

To enable editing, we must store the parsed/structured data that was used to generate
the document. This goes into `documents.metadata` (JSONB field):

```python
# When logging the document:
api_client.log_document(
    uid, "bill_to_make", session.original_filename, out.name,
    output_file_key=output_key,
    metadata={
        "parsed_data": parsed,           # the full structured data
        "bill_number": bill_data["bill_no"],
        "bill_date": bill_data["bill_date"],
        "company_info": company_info,
        "generator": "bill_to_make",     # which renderer to use
    },
)
```

### 10.3 Conversational Flow — Edit Document

```
USER: (after receiving a generated invoice)
      "Edit the BillTo name to ABC Enterprises"
───────────────────────────────────────
BOT:  ✏️ *Editing Invoice SV-0042*

      Changing *Bill To Name* from "Roorkee Scientific" to "ABC Enterprises"

      [✅ Apply & Regenerate]  [❌ Cancel]
───────────────────────────────────────
USER taps: ✅ Apply & Regenerate
───────────────────────────────────────
BOT:  ⚙️ Regenerating invoice...
BOT:  [📄 SV-0042_invoice_v2.pdf]

      ✅ *Invoice updated!*

      Changes applied:
      • Bill To Name: Roorkee Scientific → ABC Enterprises
```

### 10.4 Edit Command Structure

```python
# New BotState:
WAITING_EDIT_INSTRUCTION = "waiting_edit_instruction"
WAITING_EDIT_CONFIRM = "waiting_edit_confirm"

# After sending any generated document, add an Edit button:
reply_markup=InlineKeyboardMarkup([
    [InlineKeyboardButton("✏️ Edit this document", callback_data="edit:last")],
    [InlineKeyboardButton("📁 New File", callback_data="action:new_file"),
     InlineKeyboardButton("❌ Exit", callback_data="action:exit")],
])
```

### 10.5 Edit Parsing with LLM

Use a lightweight LLM call to interpret the edit instruction:

```python
_EDIT_PROMPT = """\
You are a document edit interpreter. Given the current document data and an edit
instruction, return a JSON object describing the change:

{
  "field_path": "bill_to.name",     // dot-notation path to the field
  "old_value": "Roorkee Scientific",
  "new_value": "ABC Enterprises",
  "confidence": 0.95
}

If the instruction is ambiguous or you can't map it to a field, return:
{"error": "description of what's unclear"}

Current document data:
{document_data}

Edit instruction: {instruction}
"""
```

### 10.6 Direct Edit Without LLM (Button-Based)

For common edits, offer a structured menu:

```python
def edit_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Edit Bill To", callback_data="edit:bill_to")],
        [InlineKeyboardButton("📦 Edit Ship To", callback_data="edit:ship_to")],
        [InlineKeyboardButton("📝 Edit Item", callback_data="edit:item")],
        [InlineKeyboardButton("🔢 Edit HSN Code", callback_data="edit:hsn")],
        [InlineKeyboardButton("📅 Edit Date", callback_data="edit:date")],
        [InlineKeyboardButton("💰 Edit Amount", callback_data="edit:amount")],
        [InlineKeyboardButton("◀ Back", callback_data="action:back_to_actions")],
    ])
```

Then each button leads to a specific prompt:
- "Edit Bill To" → "Enter the new Bill To details (Name: ..., Address: ...)"
- "Edit Item" → "Which item? (enter item number)" → "What to change?" → Apply
- "Edit HSN" → "Which item? (number)" → "Enter new HSN code"

---

## 11. Workstream 9 — Stop Swallowing Errors + Add Retry

### Problem

Throughout `bot.py`, API calls are wrapped in `try/except Exception: pass`. This means:
- Quota increments silently fail → user gets free processing
- Document logs silently fail → history is incomplete
- Profile fetches silently fail → company info missing from outputs
- No alerting, no metrics, no debugging capability

### 11.1 Add `tenacity` Retry to `api_client.py`

```python
# Add to requirements.txt:
tenacity>=8.2.0

# Wrap all API calls:
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)

@_RETRY
def get_quota(telegram_user_id: str) -> dict:
    with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT) as c:
        resp = c.get(f"{_BASE}/api/v1/auth/quota/{telegram_user_id}")
    _raise(resp)
    return resp.json()

# Apply @_RETRY to all functions:
# register_or_login, get_quota, increment_quota, get_company_profile,
# update_company_profile, upload_company_logo, get_documents, log_document,
# list_sister_formats, upload_sister_format, delete_sister_format,
# get_sister_format_file_key
```

### 11.2 Error Mapping — Technical → Human-Friendly

```python
# New file: services/bot/app/error_messages.py

_ERROR_MAP = {
    "KeyError": "We couldn't read all the data from your document. The file format may be unsupported or the document structure is unusual.",
    "JSONDecodeError": "The document parsing returned unexpected results. Please try again or use a different file.",
    "ValueError": "Some values in the document couldn't be processed. Please check the file and try again.",
    "FileNotFoundError": "The file could not be found. Please re-upload it.",
    "ConnectionError": "Could not connect to the server. Please try again in a moment.",
    "TimeoutError": "The operation took too long. Please try again with a smaller file.",
    "PermissionError": "Access denied. Please contact support.",
}

_FEATURE_HINTS = {
    "sister_quotation": "Make sure the file contains a quotation with items and prices.",
    "bill_to_make": "The file should be a DOC/DOCX with a table of items, quantities, and prices.",
    "gst_validate": "The file should be a GST invoice with line items.",
    "to_docx": "Make sure the file is a valid PDF or Excel file.",
    "to_pdf": "Make sure the file is a valid DOC, DOCX, or Excel file.",
    "bg_remove": "Make sure the image is clear and has a distinct foreground.",
}

def friendly_error(exc: Exception, feature: str = "") -> str:
    """Convert a Python exception to a user-friendly error message."""
    exc_type = type(exc).__name__
    base_msg = _ERROR_MAP.get(exc_type,
        "Something went wrong while processing your document."
    )
    hint = _FEATURE_HINTS.get(feature, "")
    msg = f"❌ {base_msg}"
    if hint:
        msg += f"\n\n💡 *Tip:* {hint}"
    msg += "\n\nYour file is still loaded — you can try another action, or send /stop to start over."
    return msg
```

### 11.3 Replace All `except Exception: pass` Blocks

Every instance in `bot.py` should be updated:

```python
# Pattern to find (14 instances in current bot.py):
try:
    api_client.increment_quota(uid)
    api_client.log_document(uid, ...)
except Exception:
    pass

# Replace with:
await _log_and_increment(uid, feature, original_filename, output_filename, output_file_key)
```

### 11.4 Error-on-Processing Behavior Change

```python
# BEFORE (aggressive reset):
except Exception as exc:
    logger.exception("feature X failed")
    await query.edit_message_text(f"❌ Failed: {exc}")
    store.reset(uid)

# AFTER (gentle recovery + friendly message):
except Exception as exc:
    logger.exception("feature X failed")
    msg = friendly_error(exc, "feature_x")
    session = store.soft_reset(uid)
    if session.pending_file:
        await query.message.reply_text(msg, parse_mode="Markdown",
            reply_markup=action_keyboard(session.pending_file.suffix.lower()))
    else:
        await query.message.reply_text(msg, parse_mode="Markdown",
            reply_markup=nav_keyboard())
```

---

## 12. Workstream 10 — Progress Indicators for Long Operations

### Problem

Operations involving LLM calls (Sister Quotation, Bill-to-Make, GST Validator,
Quotation Comparison) take 10-30 seconds. During this time, the user sees a single
"Converting..." message and silence. In a chat UI, silence means "broken."

### 12.1 Implementation — Multi-Step Progress Messages

```python
async def _with_progress(chat_or_query, steps: list[str], coroutine):
    """Run a coroutine while showing progress steps to the user."""
    msg = None
    for i, step in enumerate(steps):
        text = f"⏳ {step} ({i+1}/{len(steps)})"
        if msg is None:
            if hasattr(chat_or_query, 'edit_message_text'):
                await chat_or_query.edit_message_text(text)
                msg = chat_or_query
            else:
                msg = await chat_or_query.reply_text(text)
        else:
            try:
                await msg.edit_text(text)
            except Exception:
                pass
        if i < len(steps) - 1:
            await asyncio.sleep(0.3)  # brief pause so user sees each step

    result = await coroutine
    return result
```

### 12.2 Feature-Specific Progress Steps

```python
# Sister Quotation:
steps = [
    "📖 Reading your document...",
    "🔍 Extracting items and prices...",
    "📐 Applying your format template...",
    "📄 Generating DOCX output...",
]

# Bill to Make:
steps = [
    "📖 Reading document text...",
    "🤖 AI is extracting line items...",
    "🧮 Calculating GST and totals...",
    "📄 Rendering invoice PDF...",
]

# GST Validator:
steps = [
    "📖 Reading invoice content...",
    "🤖 AI is analyzing GST details...",
    "✅ Checking math and HSN codes...",
]

# Quotation Comparison:
steps = [
    f"📖 Reading {n} quotation files...",
    "🤖 AI is extracting items from each...",
    "📊 Building comparison table...",
    "📄 Generating DOCX output...",
]
```

### 12.3 Implementation Pattern for Bill to Make

```python
async def _do_bill_to_make(update, uid, session, text):
    # ... (parse bill_no, date — existing code) ...

    # Show Step 1
    progress_msg = await update.message.reply_text("⏳ Reading document text... (1/4)")

    # Parse
    doc_text = await asyncio.get_event_loop().run_in_executor(
        None, lambda: extract_text(session.pending_file)
    )

    # Show Step 2
    await progress_msg.edit_text("🤖 AI is extracting line items... (2/4)")
    parsed = await asyncio.get_event_loop().run_in_executor(
        None, lambda: parse_bill_doc_text(api_key, model, doc_text)
    )

    # Show Step 3 (will happen in HSN/BillTo check if needed)
    await progress_msg.edit_text("🧮 Checking for missing details... (3/4)")

    # Continue to HSN check...
```

---

## 13. Workstream 11 — UX Polish & Copy Improvements

### 13.1 Remove Dead Code

**`format_keyboard()`** — This function in `keyboards.py` (lines 51-60) uses hardcoded
Sanmati-era format names (`sv_enterprises`, `sanmati`, `nr_survey`). It's replaced by
`sister_format_keyboard()`. Remove it and any references.

### 13.2 Fix `/upgrade` Dead End

Add a handler:

```python
async def cmd_upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "💎 *Upgrade Your Plan*\n\n"
        "| Plan | Price | Docs/month |\n"
        "| Free | ₹0 | 10 |\n"
        "| Starter | ₹499/mo | 100 |\n"
        "| Pro | ₹1,499/mo | 500 |\n"
        "| Business | ₹3,999/mo | Unlimited |\n\n"
        "To upgrade, contact us:\n"
        "📧 support@docseva.in\n"
        "📞 +91-XXXXXXXXXX\n\n"
        "_Online payment coming soon!_",
        parse_mode="Markdown",
    )

# Register:
app.add_handler(CommandHandler("upgrade", cmd_upgrade))
```

### 13.3 Improve Onboarding Copy

Make optional fields visually obvious:

```python
# BEFORE:
"What is your *business phone number*? (or type /skip to add later)"

# AFTER:
"What is your *business phone number*?\n\n"
"_This is optional — tap /skip if you'd like to add it later._\n"
"_Your phone won't be shared. It appears on your invoices._"
```

### 13.4 Contextual Help Instead of Wall of Text

Replace the `/help` command dump with a shorter message + "Learn more" buttons:

```python
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "*DocSeva Help* 🤖\n\n"
        "Just send me any file and I'll show you what I can do with it!\n\n"
        "🆕 *New:* You can now create invoices and quotations from scratch — type /create\n\n"
        "Quick commands:\n"
        "• /create — create a new document\n"
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
```

### 13.5 Welcome Back Message — Show What's New

```python
# When a returning user sends /start:
"👋 Welcome back to *DocSeva*, {company}!\n\n"
"📊 {used}/{limit} docs used this month\n\n"
"🆕 *What's new:*\n"
"• Create invoices from scratch — /create\n"
"• Edit generated documents\n"
"• Download files from /history\n\n"
"Send me a file or type /create to start."
```

---

## 14. Workstream 12 — Session & File Durability

### Problem

Multi-file flows (quotation comparison) store file paths in the session. These paths
point to `/tmp` files that don't survive container restarts. Also, if the bot container
restarts mid-flow, the files are lost even though the session state is in Redis.

### 14.1 Upload Input Files to MinIO During Multi-File Flows

For comparison flows, upload each file to MinIO as it's received:

```python
async def _add_comparison_file(update, ctx, uid, session, doc, suffix):
    # ... download to local ...

    # Upload to MinIO for durability
    input_key = None
    try:
        from app.storage_client import upload_input
        input_key = await asyncio.get_event_loop().run_in_executor(
            None, lambda: upload_input(session.org_id, str(uuid.uuid4()), local)
        )
    except Exception:
        pass

    session.comparison_files.append({
        "path": str(local),       # local path for current processing
        "name": doc.file_name,
        "minio_key": input_key,   # MinIO key for durability
    })
```

### 14.2 Persist File Paths in Redis Session

Add `comparison_files` to `_PERSISTABLE_FIELDS` so multi-file flows survive restarts:

```python
_PERSISTABLE_FIELDS = {
    "state", "is_registered", "user_id", "org_id", "company_profile",
    "onboarding_name", "onboarding_company",
    "original_filename",
    "pending_quote_stem", "pending_bill_data",
    "comparison_total", "comparison_files",  # ← ADD
    "updating_field",
    "pending_watermark_mode",
    "pending_create_invoice",  # ← ADD (for WS-3)
}
```

### 14.3 Recovery on Restart

When restoring a session from Redis that has file paths, check if local files exist.
If not, download from MinIO:

```python
async def _ensure_local_file(session, uid) -> bool:
    """Ensure pending_file exists locally. Re-download from MinIO if needed."""
    if session.pending_file and Path(session.pending_file).exists():
        return True
    # File lost (container restart). Check if we have a MinIO key.
    # For now, notify user and reset.
    return False
```

---

## 15. End-to-End Workflow Map

```
                            ┌──────────────────┐
                            │  /create command  │
                            └────────┬─────────┘
                                     │
                   ┌─────────────────┼─────────────────┐
                   ▼                 ▼                  ▼
            ┌──────────┐     ┌──────────┐      ┌──────────┐
            │  Create   │     │  Create   │      │  Create   │
            │ Invoice   │     │ Quotation │      │    PO     │
            └─────┬────┘     └─────┬────┘      └─────┬────┘
                  │                │                   │
                  ▼                ▼                   ▼
            ┌──────────┐     ┌──────────┐      ┌──────────┐
            │Generated │     │Generated │      │Generated │
            │Invoice   │     │Quotation │      │   PO     │
            │  (PDF)   │     │  (DOCX)  │      │  (PDF)   │
            └──┬──┬────┘     └──┬──┬────┘      └──┬──┬────┘
               │  │              │  │               │  │
    ┌──────────┘  └──────┐      │  └──────┐        │  └──────┐
    ▼                    ▼      ▼          ▼       ▼          ▼
┌────────┐         ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Validate│         │ Edit   │ │Sister  │ │Create  │ │Create  │
│  GST   │         │Document│ │ Quote  │ │  PO    │ │Invoice │
└────────┘         └────────┘ └────────┘ └────────┘ └────────┘

                    ┌──────────────────┐
                    │  Upload any file │
                    └────────┬─────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
              ┌──────────┐     ┌──────────┐
              │Doc/PDF   │     │  Image   │
              │  Actions │     │ Actions  │
              └──┬───────┘     └──┬───────┘
                 │                 │
     ┌───┬───┬───┼───┬───┐     ┌──┼───┬──────┐
     ▼   ▼   ▼   ▼   ▼   ▼     ▼  ▼   ▼      ▼
   Sister Bill  PDF  GST Cmp  Rename WM  BG  Catalog
   Quote  Make  Conv Val       Rem  Logo
```

---

## 16. Database Migration Plan

### Migration 003: Add PO and Quotation Counters + New Columns

```python
# alembic/versions/003_v2_features.py

def upgrade():
    # Add PO tracking to company_profiles
    op.add_column('company_profiles', sa.Column('po_prefix', sa.Text(), server_default='PO'))
    op.add_column('company_profiles', sa.Column('po_counter', sa.Integer(), server_default='1'))
    op.add_column('company_profiles', sa.Column('quotation_prefix', sa.Text(), server_default='QT'))
    op.add_column('company_profiles', sa.Column('quotation_counter', sa.Integer(), server_default='1'))

    # Add input_file_key to documents (for storing uploaded inputs)
    op.add_column('documents', sa.Column('input_file_key', sa.Text(), nullable=True))

    # Add source_document_id for workflow chaining (e.g., PO → Invoice)
    op.add_column('documents', sa.Column('source_document_id',
        sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_doc_source', 'documents', 'documents',
        ['source_document_id'], ['id'], ondelete='SET NULL')

    # Add document_type for easier querying
    op.add_column('documents', sa.Column('document_type', sa.Text(), nullable=True))
    # Values: 'invoice', 'quotation', 'po', 'sister_quotation', 'comparison', etc.
```

### Updated Models

```python
class Document(Base):
    # ... existing fields ...
    input_file_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    document_type: Mapped[str | None] = mapped_column(Text, nullable=True)

class CompanyProfile(Base):
    # ... existing fields ...
    po_prefix: Mapped[str] = mapped_column(Text, default="PO")
    po_counter: Mapped[int] = mapped_column(Integer, default=1)
    quotation_prefix: Mapped[str] = mapped_column(Text, default="QT")
    quotation_counter: Mapped[int] = mapped_column(Integer, default=1)
```

---

## 17. API Contract Changes

### 17.1 New Endpoint: Download Document Output

```
GET /api/v1/documents/{telegram_user_id}/{document_id}/download
→ 302 Redirect to presigned MinIO URL
→ 404 if document not found or output_file_key is null
```

### 17.2 New Endpoint: Get Document Metadata (for editing)

```
GET /api/v1/documents/{telegram_user_id}/{document_id}/metadata
→ 200 { "parsed_data": {...}, "generator": "bill_to_make", ... }
```

### 17.3 Updated Document Log Request

```python
class DocumentLogRequest(BaseModel):
    feature: str
    original_filename: str | None = None
    output_filename: str | None = None
    output_file_key: str | None = None
    input_file_key: str | None = None        # NEW
    source_document_id: str | None = None     # NEW — UUID of parent doc
    document_type: str | None = None          # NEW — invoice/quotation/po/etc.
    metadata: dict[str, Any] = {}
    status: str = "completed"
    error_message: str | None = None
```

### 17.4 Updated Profile Schema

```python
class CompanyProfileUpdate(BaseModel):
    # ... existing fields ...
    po_prefix: str | None = None         # NEW
    quotation_prefix: str | None = None  # NEW

class CompanyProfileOut(BaseModel):
    # ... existing fields ...
    po_prefix: str               # NEW
    po_counter: int              # NEW
    quotation_prefix: str        # NEW
    quotation_counter: int       # NEW
```

### 17.5 New Endpoint: Increment Counter

```
POST /api/v1/profile/{telegram_user_id}/increment-counter
Body: { "counter_type": "invoice" | "po" | "quotation" }
→ 200 { "new_value": 43 }
```

---

## 18. Bot State Machine — Complete Updated Diagram

```
                              ┌─────────┐
                    /start ──►│ONBOARDING│
                              │ _NAME   │
                              └────┬────┘
                                   │ text
                              ┌────▼────┐
                              │ONBOARDING│
                              │_COMPANY │
                              └────┬────┘
                                   │ text
                              ┌────▼────┐
                              │ONBOARDING│
                              │ _PHONE  │
                              └────┬────┘
                                   │ text or /skip
                              ┌────▼────┐
                              │ONBOARDING│
                              │ _GSTIN  │
                              └────┬────┘
                                   │ text or /skip
                ┌──────────────────▼──────────────────┐
                │              IDLE                    │
                │  (Accepts: file, /command, /create)  │
                └────┬─────────────┬──────────────────┘
                     │ file        │ /create
              ┌──────▼──────┐  ┌──▼──────────────────┐
              │WAITING_ACTION│  │CREATE MENU           │
              │(button tap) │  │(invoice/quote/po)    │
              └──┬──────────┘  └──┬────────────────────┘
                 │                 │
    ┌────┬───┬───┼───┬────┐       ├──► CREATING_INVOICE_BILLTO
    ▼    ▼   ▼   ▼   ▼    ▼       │      → CREATING_INVOICE_ITEMS
  Sister Bill GST Cmp  WM  ...    │      → CREATING_INVOICE_HSN
  Quote Make Val              │      → CREATING_INVOICE_GST_TYPE
    │    │    │    │    │       │      → CREATING_INVOICE_CONFIRM
    │    │    │    │    │       │
    │    ├──► WAITING_BILL_META │   ├──► CREATING_PO_VENDOR
    │    │    → WAITING_BILL_HSN│       → CREATING_PO_ITEMS
    │    │    → WAITING_BILL_TO │       → CREATING_PO_TERMS
    │    │    → generate        │       → CREATING_PO_CONFIRM
    │    │                      │
    │    │                      ├──► CREATING_QUOTE_TEMPLATE
    │    │                             → CREATING_QUOTE_CUSTOMER
    │    │                             → CREATING_QUOTE_ITEMS
    │    │                             → CREATING_QUOTE_TERMS
    │    │                             → CREATING_QUOTE_CONFIRM
    │    │
    │    ├──► WAITING_BILL_META
    │         → WAITING_BILL_HSN
    │         → WAITING_BILL_TO_DETAILS
    │         → generate PDF
    │
    ├──► WAITING_FORMAT / sister_format_keyboard
    │    → convert + WAITING_PRICE_ADJUST
    │      → WAITING_PRICE_CUSTOM (if custom %)
    │
    ├──► WAITING_COMPARISON_COUNT
    │    → WAITING_COMPARISON_CUSTOM_COUNT
    │    → WAITING_COMPARISON_FILES (collect N files)
    │
    ├──► WAITING_WATERMARK_MODE → WAITING_WATERMARK_TEXT
    │
    ├──► WAITING_RENAME (text → rename → done)
    │
    ├──► WAITING_CATALOG_DETAILS (text → generate → done)
    │
    └──► WAITING_EDIT_INSTRUCTION → WAITING_EDIT_CONFIRM (NEW)

    /settings ──► UPDATING_PROFILE_FIELD
    /formats  ──► WAITING_SISTER_FORMAT_FILE → WAITING_SISTER_FORMAT_NAME

    Every terminal state returns to IDLE (or WAITING_ACTION if file preserved)
    /stop from ANY state → IDLE (hard reset)
```

---

## 19. Error Code Catalogue

| Code | User Message | Technical Cause | Recovery |
|------|-------------|----------------|----------|
| E001 | "We couldn't read the data from your document. The format may be unsupported." | KeyError / parsing failure | soft_reset, show action keyboard |
| E002 | "The AI couldn't understand this document. Please try a clearer file." | LLM returned invalid JSON | soft_reset, show action keyboard |
| E003 | "The file appears to be corrupted or empty." | Empty text extraction | soft_reset |
| E004 | "Your monthly quota is exhausted ({used}/{limit})." | Quota check failed | Show /upgrade |
| E005 | "Could not connect to the server. Please try again." | API connection error | Auto-retry 3x, then show message |
| E006 | "The file is too large ({size} MB). Maximum is 15 MB." | Size validation | No reset needed |
| E007 | "This file type is not supported." | Extension check | No reset needed |
| E008 | "Processing took too long. Please try a smaller file." | Timeout | soft_reset |
| E009 | "Something went wrong. Your file is still loaded — try another action." | Generic unhandled | soft_reset, show action keyboard |
| E010 | "The format template could not be downloaded." | MinIO download failure | Keep in current state |

---

## 20. Testing Strategy

### 20.1 New Test Modules Needed

| Module | Tests | Workstream |
|--------|-------|-----------|
| `test_output_storage.py` | Upload output to MinIO, verify key stored in document log, verify presigned URL generation | WS-1 |
| `test_state_handling.py` | Every BotState receives wrong input type → verify correct hint message, verify /stop works from every state | WS-2 |
| `test_create_invoice.py` | Full flow: BillTo → Items → HSN → GST → Confirm → PDF, edge cases (no items, invalid amounts, skip HSN) | WS-3 |
| `test_po_generator.py` | PO from quotation file, PO from scratch, PO PDF rendering | WS-4 |
| `test_scratch_quotation.py` | Template selection, item entry, terms, DOCX generation | WS-5 |
| `test_bill_from_po.py` | Chain: PO → Invoice, data mapping verification | WS-6 |
| `test_gst_auto_validate.py` | Structured data validation, GSTIN format, math checks | WS-7 |
| `test_document_editing.py` | Edit BillTo, edit item, edit HSN, re-render | WS-8 |
| `test_error_handling.py` | Retry behavior, error mapping, soft_reset vs hard reset | WS-9 |
| `test_progress.py` | Progress message sequence verification | WS-10 |
| `test_workflow_chain.py` | Full chain: Create Quote → Sister → PO → Invoice → GST Validate | WS-3,4,5,6,7 |

### 20.2 Test Pattern for Conversational Flows

```python
async def test_create_invoice_full_flow(mock_update, mock_context, store):
    """Test the complete create-invoice-from-scratch flow."""
    uid = "12345"

    # Step 1: User sends /create
    await cmd_create(mock_update, mock_context)
    assert "Create a New Document" in mock_update.message.reply_text.call_args[0][0]

    # Step 2: User taps "Create Invoice"
    mock_update.callback_query.data = "create:invoice"
    await handle_callback(mock_update, mock_context)
    session = store.get(uid)
    assert session.state == BotState.CREATING_INVOICE_BILLTO

    # Step 3: User sends BillTo details
    mock_update.message.text = "Name: Test Corp\nAddress: 123 Main St\nGSTIN: NA\nState: Delhi"
    await handle_text(mock_update, mock_context)
    session = store.get(uid)
    assert session.state == BotState.CREATING_INVOICE_ITEMS
    assert session.pending_create_invoice.bill_to["name"] == "Test Corp"

    # ... continue through all steps ...
```

### 20.3 Coverage Targets

| Area | Current | Target |
|------|---------|--------|
| `bot.py` | ~45% | 80% |
| `processors/` | ~70% | 85% |
| New create flows | 0% | 90% |
| Error handling | ~30% | 85% |
| State transitions | ~50% | 95% |

---

## 21. Rollout Plan

### Phase 1 — Foundation (Week 1)

| Day | Work | Deliverable |
|-----|------|-------------|
| 1 | WS-1: Wire up MinIO output storage | All outputs stored, `/history` has download links |
| 1 | WS-9: Add tenacity + error mapping | No more silent failures |
| 2-3 | WS-2: State-aware input handling | Every state handles unexpected input gracefully |
| 3 | WS-10: Progress indicators | All LLM operations show step progress |
| 3 | WS-11: UX polish (dead code, /upgrade, copy) | Clean UI, no dead ends |

### Phase 2 — Create Workflows (Week 2)

| Day | Work | Deliverable |
|-----|------|-------------|
| 4-5 | WS-3: Create Invoice from scratch | Full guided invoice creation flow |
| 5-6 | WS-12: Session durability | Multi-file flows survive restarts |
| 6-7 | DB migration 003 | New columns for PO, quotation counters |

### Phase 3 — Workflow Chain (Week 3)

| Day | Work | Deliverable |
|-----|------|-------------|
| 8-9 | WS-5: Sister Quotation from scratch | Default templates, guided flow |
| 9-10 | WS-4: PO Generator | From file and from scratch |
| 11 | WS-6: Bill from PO/Quotation | Chained generation |
| 11 | WS-7: GST auto-validate | Post-generation validation |

### Phase 4 — Edit & Polish (Week 4)

| Day | Work | Deliverable |
|-----|------|-------------|
| 12-14 | WS-8: Document editing | Button-based editing of generated docs |
| 14-15 | Integration testing | Full workflow chain E2E tests |
| 15 | Release candidate | All features tested, documented |

---

## Appendix A — Full Conversational Scripts

### A.1 — Unexpected Input During Comparison Flow

```
USER uploads: quotation_1.pdf
BOT:  📂 *quotation_1.pdf* received. What would you like to do?
      [📊 Compare Quotations] ...
───────────────────────────────────────
USER taps: 📊 Compare Quotations
BOT:  📊 How many quotations to compare?
      [2] [3] [4] [5] [Custom]
───────────────────────────────────────
USER taps: [3]
BOT:  📊 Great! I have quotation 1/3. Please send the next 2 files one by one.
───────────────────────────────────────
USER sends TEXT: "what formats do you support?"
───────────────────────────────────────
BOT:  I'm waiting for quotation 2 of 3.
      Please send a document file (DOC, DOCX, PDF, or Excel).

      💡 Need help? Send /stop to cancel the comparison first, then /help.
───────────────────────────────────────
USER uploads: quotation_2.xlsx
BOT:  ✅ Got quotation 2/3. Please send the next one.
───────────────────────────────────────
USER uploads: photo.jpg  (wrong type)
───────────────────────────────────────
BOT:  ⚠️ I need a document file for comparison, not an image.
      Please send a DOC, DOCX, PDF, or Excel file as quotation 3/3.
```

### A.2 — Error Recovery with File Preserved

```
USER uploads: messy_doc.docx
BOT:  📂 *messy_doc.docx* received. What would you like to do?
      [📋 Sister Quotation] [🧾 Bill to Make] ...
───────────────────────────────────────
USER taps: 🧾 Bill to Make
BOT:  Enter bill number and date: `BILL_NO, DD-MM-YYYY`
USER: INV-001, 31-05-2026
BOT:  ⏳ Reading document text... (1/4)
BOT:  🤖 AI is extracting line items... (2/4)
BOT:  ❌ We couldn't read the items from your document. The format may be
      unsupported or the document structure is unusual.

      💡 The file should contain a table with item names, quantities, and prices.

      Your file is still loaded — you can try another action:
      [📋 Sister Quotation] [🧾 Bill to Make] [📄 PDF→DOCX] ...
      [📁 New File] [❌ Exit]
───────────────────────────────────────
USER taps: 📄 PDF→DOCX   (tries a different action — no re-upload needed!)
```

### A.3 — File Replacement Confirmation

```
USER uploads: file_A.pdf
BOT:  📂 *file_A.pdf* received. What would you like to do?
      [📋 Sister Quotation] ...
───────────────────────────────────────
USER uploads: file_B.pdf  (sends another file without choosing an action)
───────────────────────────────────────
BOT:  You already have *file_A.pdf* loaded.

      Do you want to replace it with *file_B.pdf*?

      [✅ Yes, use new file]  [❌ No, keep current]
───────────────────────────────────────
USER taps: [✅ Yes, use new file]
BOT:  📂 *file_B.pdf* loaded. What would you like to do?
      [📋 Sister Quotation] ...
```

### A.4 — Go Back in Bill to Make

```
USER uploads: supply_list.docx
BOT:  📂 *supply_list.docx* received. What would you like to do?
USER taps: 🧾 Bill to Make
BOT:  Enter bill number and date...
USER: INV-099, 31-05-2026
BOT:  (parses doc, finds missing HSN)
      🔢 HSN/SAC Codes Required (2 of 5 items)
      1. Digital pH Meter
      3. Calibration Kit
      Enter codes or type `skip`.
      [⏭ Skip] [◀ Back to actions] [❌ Cancel]
───────────────────────────────────────
USER taps: [◀ Back to actions]
───────────────────────────────────────
BOT:  📂 *supply_list.docx* is still loaded.
      What would you like to do?
      [📋 Sister Quotation] [🧾 Bill to Make] ...
```

---

## Appendix B — Keyboard Definitions

### B.1 New Keyboards

```python
def create_menu_keyboard() -> InlineKeyboardMarkup:
    """Main create-from-scratch menu."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Create Invoice / Bill", callback_data="create:invoice")],
        [InlineKeyboardButton("📋 Create Quotation", callback_data="create:quotation")],
        [InlineKeyboardButton("📦 Create Purchase Order", callback_data="create:po")],
        [InlineKeyboardButton("◀ Back to Menu", callback_data="action:exit")],
    ])

def create_invoice_items_keyboard() -> InlineKeyboardMarkup:
    """After items are entered in create-invoice flow."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add More Items", callback_data="cinv:more_items")],
        [InlineKeyboardButton("✏️ Edit Items", callback_data="cinv:edit_items")],
        [InlineKeyboardButton("▶️ Continue", callback_data="cinv:continue")],
        [InlineKeyboardButton("❌ Cancel", callback_data="action:new_file")],
    ])

def gst_rate_keyboard() -> InlineKeyboardMarkup:
    """GST rate selection for create flows."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("5%", callback_data="gst:5"),
            InlineKeyboardButton("12%", callback_data="gst:12"),
            InlineKeyboardButton("18%", callback_data="gst:18"),
            InlineKeyboardButton("28%", callback_data="gst:28"),
        ],
        [
            InlineKeyboardButton("✏️ Custom Rate", callback_data="gst:custom"),
            InlineKeyboardButton("🔀 Per-Item Rate", callback_data="gst:per_item"),
        ],
        [InlineKeyboardButton("◀ Back", callback_data="cinv:back_items")],
    ])

def invoice_confirm_keyboard() -> InlineKeyboardMarkup:
    """Final confirmation before generating invoice."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Generate Invoice PDF", callback_data="cinv:generate")],
        [InlineKeyboardButton("✏️ Edit", callback_data="cinv:edit")],
        [InlineKeyboardButton("❌ Cancel", callback_data="action:new_file")],
    ])

def post_generation_keyboard(doc_type: str = "invoice") -> InlineKeyboardMarkup:
    """Actions available after generating a document."""
    rows = []
    if doc_type == "invoice":
        rows.append([InlineKeyboardButton("✅ Validate GST", callback_data="action:gst_auto")])
        rows.append([InlineKeyboardButton("✏️ Edit this invoice", callback_data="edit:last")])
    elif doc_type == "quotation":
        rows.append([InlineKeyboardButton("📋 Create Sister Quotation", callback_data="chain:sister")])
        rows.append([InlineKeyboardButton("📦 Create PO from this", callback_data="chain:po")])
        rows.append([InlineKeyboardButton("✏️ Edit this quotation", callback_data="edit:last")])
    elif doc_type == "po":
        rows.append([InlineKeyboardButton("🧾 Create Invoice from PO", callback_data="chain:invoice")])
        rows.append([InlineKeyboardButton("✏️ Edit this PO", callback_data="edit:last")])
    rows.append([
        InlineKeyboardButton("📁 New File", callback_data="action:new_file"),
        InlineKeyboardButton("❌ Exit", callback_data="action:exit"),
    ])
    return InlineKeyboardMarkup(rows)

def edit_menu_keyboard() -> InlineKeyboardMarkup:
    """Edit options for a generated document."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Edit Bill To / Customer", callback_data="edit:bill_to")],
        [InlineKeyboardButton("📦 Edit Ship To", callback_data="edit:ship_to")],
        [InlineKeyboardButton("📝 Edit Item Name/Price", callback_data="edit:item")],
        [InlineKeyboardButton("🔢 Edit HSN Code", callback_data="edit:hsn")],
        [InlineKeyboardButton("📅 Edit Date", callback_data="edit:date")],
        [InlineKeyboardButton("🔢 Edit Invoice Number", callback_data="edit:number")],
        [InlineKeyboardButton("◀ Back", callback_data="action:back_to_actions")],
    ])

def delivery_terms_keyboard() -> InlineKeyboardMarkup:
    """PO delivery terms selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚚 Ex-Works", callback_data="delivery:ex_works"),
            InlineKeyboardButton("🏭 FOR Dest", callback_data="delivery:for_dest"),
        ],
        [InlineKeyboardButton("✏️ Custom Terms", callback_data="delivery:custom")],
        [InlineKeyboardButton("◀ Back", callback_data="po:back_items")],
    ])

def quotation_template_keyboard() -> InlineKeyboardMarkup:
    """Built-in template selection for scratch quotations."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📐 Professional — clean & modern", callback_data="qtpl:professional")],
        [InlineKeyboardButton("📊 Compact — dense, more items", callback_data="qtpl:compact")],
        [InlineKeyboardButton("🏛 Government — formal tender", callback_data="qtpl:government")],
        [InlineKeyboardButton("📤 Upload my own template", callback_data="qtpl:custom")],
        [InlineKeyboardButton("◀ Back", callback_data="action:exit")],
    ])
```

### B.2 Updated `action_keyboard` — Add PO Button

```python
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
            [InlineKeyboardButton("📦 Generate Purchase Order", callback_data="action:create_po")],  # NEW
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
```

---

## Summary — Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `services/bot/app/error_messages.py` | Error mapping: technical → user-friendly |
| `services/bot/app/handlers/create_invoice.py` | Create-invoice-from-scratch flow handler |
| `services/bot/app/handlers/create_quotation.py` | Create-quotation-from-scratch flow handler |
| `services/bot/app/handlers/create_po.py` | Create-PO flow handler |
| `services/bot/app/handlers/edit_document.py` | Document editing flow handler |
| `services/bot/app/processors/po_generator.py` | PO PDF renderer |
| `services/bot/app/processors/quotation_generator.py` | Quotation DOCX renderer using docxtpl |
| `services/api/app/tasks/cleanup.py` | Expired document cleanup task |
| `assets/templates/quotation_professional.docx` | Built-in template |
| `assets/templates/quotation_compact.docx` | Built-in template |
| `assets/templates/quotation_government.docx` | Built-in template |
| `alembic/versions/003_v2_features.py` | DB migration |
| Tests: 11 new test modules | See Section 20 |

### Modified Files

| File | Changes |
|------|---------|
| `services/bot/app/bot.py` | Add /create command, upload outputs, soft_reset, progress indicators, state-aware fallback, post-generation keyboards, workflow chaining callbacks |
| `services/bot/app/keyboards.py` | Remove `format_keyboard()`, add all new keyboards from Appendix B, update `action_keyboard` with PO button |
| `services/bot/app/session_store.py` | Add new BotState values, add `CreateInvoiceData`/`PurchaseOrderData` to UserSession, add `soft_reset()` method, expand `_PERSISTABLE_FIELDS` |
| `services/bot/app/api_client.py` | Add `@_RETRY` decorator to all functions, add `increment_counter()` function |
| `services/bot/app/storage_client.py` | Update `upload_output()` signature (add doc_id), add `upload_input()` |
| `services/bot/app/utils.py` | Add `parse_invoice_items()`, `_parse_number()` |
| `services/bot/app/handlers/onboarding.py` | Improve optional field copy |
| `services/bot/requirements.txt` | Add `tenacity>=8.2.0` |
| `services/api/app/models/models.py` | Add new columns to CompanyProfile and Document |
| `services/api/app/schemas/schemas.py` | Update request/response schemas |
| `services/api/app/routes/documents.py` | Add download and metadata endpoints |
| `services/api/app/routes/profile.py` | Add increment-counter endpoint |

---

*End of Document — DocSeva v2 Product & Technical Specification*
*Version 1.0 — 31 May 2026*
