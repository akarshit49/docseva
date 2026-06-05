# Execution Plan — Multi-Channel Platform for Instrument/Equipment Dealers

> **For:** System Architect & Senior Engineers
>
> **Goal:** Complete the existing bot, add a Web App that does the same things, and add
> WhatsApp as a channel — all sharing **one** backend, **one** processing engine, and
> **one** data model. The user picks whichever channel they prefer; the product behaves
> the same.
>
> **Vertical:** Dealers / traders / manufacturers of scientific, lab, industrial, medical,
> electrical instruments — businesses whose daily job is **turning supplier quotes into
> their own branded customer quotes** (and the closing tasks around that).
>
> **Headline (anchor) feature:** "Supplier quote → your branded customer quote in under
> 2 minutes." Everything else is supporting toolkit or hidden utility.
>
> **Last updated:** 1 June 2026

---

## Table of Contents

1. [Architecture Principles (the rules everything follows)](#1-architecture-principles)
2. [Target Architecture — Channels Over a Shared Core](#2-target-architecture)
3. [Feature Hierarchy — What Each Channel Shows](#3-feature-hierarchy)
4. [Workstreams Overview & Sequencing](#4-workstreams-overview--sequencing)
5. [WS-A · Backend: Unified Identity, Auth & Channels](#5-ws-a--backend-unified-identity-auth--channels)
6. [WS-B · Backend: Output Storage, Retry, Errors, Counters](#6-ws-b--backend-output-storage-retry-errors-counters)
7. [WS-C · Backend: Generic "Process Document" API](#7-ws-c--backend-generic-process-document-api)
8. [WS-D · Telegram Bot: Completion & Reframe to Anchor](#8-ws-d--telegram-bot-completion--reframe-to-anchor)
9. [WS-E · WhatsApp Bot Channel](#9-ws-e--whatsapp-bot-channel)
10. [WS-F · Web App: Architecture & Stack](#10-ws-f--web-app-architecture--stack)
11. [WS-G · Web App: Information Architecture & Screens](#11-ws-g--web-app-information-architecture--screens)
12. [WS-H · Web App: Anchor Flow UX](#12-ws-h--web-app-anchor-flow-ux)
13. [WS-I · Web App: Other Screens (toolkit, utilities, history, settings)](#13-ws-i--web-app-other-screens)
14. [WS-J · Cross-Channel Parity Matrix](#14-ws-j--cross-channel-parity-matrix)
15. [Data Model Changes](#15-data-model-changes)
16. [API Contract Additions](#16-api-contract-additions)
17. [Design System & UX Standards](#17-design-system--ux-standards)
18. [Observability, Security, Compliance](#18-observability-security-compliance)
19. [Testing Strategy](#19-testing-strategy)
20. [Release Plan & Sprint Breakdown](#20-release-plan--sprint-breakdown)
21. [Definition of Done (per workstream)](#21-definition-of-done)
22. [Appendix A — Anchor Flow Wireframe (Web)](#appendix-a--anchor-flow-wireframe-web)
23. [Appendix B — Telegram/WhatsApp Anchor Scripts](#appendix-b--telegramwhatsapp-anchor-scripts)

---

## 1. Architecture Principles

These rules are not negotiable. Every PR must respect them.

1. **One brain, many faces.** All document logic (sister quotation, bill-to-make,
   comparison, GST validation, conversions) lives in the API service. Channels
   (Telegram, WhatsApp, Web) are thin adapters — UI + uploads/downloads + state.
2. **Channels never duplicate business logic.** If you find yourself porting a `processor`
   into the web frontend or WhatsApp adapter, stop — refactor it into a backend endpoint.
3. **Identity is unified.** A user is one `User`; channel handles (telegram_user_id,
   whatsapp_e164, email) are *links* to that user, not separate users.
4. **Anchor first, toolkit second, utilities hidden.** Every channel's first impression
   must showcase the anchor feature. The 12 historical features still exist, but their
   visibility is tiered.
5. **Confirm before send.** Anywhere AI extracts data that becomes a customer-facing
   document, the user MUST review and confirm a structured summary before the final
   document is produced.
6. **Same backend, same outputs.** A quote generated on the Web app and a quote generated
   on Telegram from the same inputs must produce byte-identical (or near-identical) PDFs.
   This is enforced by routing both through the same `processor` modules.
7. **No silent failures.** Every API call retries; every failure logs with context;
   every user-facing error is human-readable. (Replaces the current `except Exception: pass`
   pattern entirely.)

---

## 2. Target Architecture

```
                ┌────────────────────────────────────────────────────────┐
                │                  USER (dealer / trader)                 │
                └────────────────────────────────────────────────────────┘
                          │                  │                 │
                          ▼                  ▼                 ▼
                   ┌────────────┐    ┌────────────┐    ┌────────────┐
                   │  Web App   │    │  Telegram  │    │  WhatsApp  │
                   │ (Next.js)  │    │    Bot     │    │    Bot     │
                   └─────┬──────┘    └─────┬──────┘    └─────┬──────┘
                         │                  │                 │
            JWT (Bearer) │  X-Bot-Token     │  X-Bot-Token    │
                         └────────────┬─────┴─────────────────┘
                                      ▼
                          ┌──────────────────────────┐
                          │     FastAPI (the brain)   │
                          │                           │
                          │  /auth   /profile         │
                          │  /documents  /quotes      │
                          │  /sister-formats          │
                          │  /process/<feature>       │  ← NEW generic endpoint
                          │  /channels                │  ← NEW (link handles)
                          └──┬───────┬────────────┬───┘
                             │       │            │
                       ┌─────▼─┐  ┌──▼──┐    ┌────▼────┐
                       │  PG   │  │Redis │    │  MinIO  │
                       └───────┘  └─────┘    └─────────┘
                             │       │            │
                             └───────┴────────────┘
                                     │
                              ┌──────▼──────┐
                              │ Processors  │
                              │ (Python)    │
                              │ sister_quote│
                              │ bill_to_make│
                              │ compare     │
                              │ gst_validate│
                              │ conversions │
                              │ ...         │
                              └─────────────┘
```

### Key consequences

- The existing `services/bot/app/processors/` modules **move into the API service** (or are
  invoked via a shared package). The web and WhatsApp channels must not re-implement them.
- The current `services/api/` keeps its routes; we add `/process/<feature>` and `/channels`.
- The current Telegram bot becomes one of three thin channels. Its job is: handle
  Telegram-specific UI + uploads, then call the API.
- New WhatsApp service: identical job, for WhatsApp.
- New Web service: identical job, for browsers.

### Repository layout (target)

```
DocSeva/
├── services/
│   ├── api/                ← FastAPI (the brain + processors)
│   │   └── app/processors/ ← MOVED here from bot/ for reuse
│   ├── bot-telegram/       ← (renamed from `bot/`) — thin Telegram adapter
│   ├── bot-whatsapp/       ← NEW — thin WhatsApp adapter
│   └── web/                ← NEW — Next.js app
├── shared/
│   └── pyproject.toml      ← Shared Pydantic schemas (optional)
└── ...
```

---

## 3. Feature Hierarchy

This hierarchy is the most important UX decision in the whole plan. Every channel must
respect it.

### Tier 1 — Anchor (the headline, always visible first)

| Feature | Description |
|---|---|
| **Sister Quotation** | Upload a supplier's quote (PDF/DOC/DOCX/image of paper quote) → confirm extracted items → output a branded customer quotation PDF/DOCX in your saved tender format. |

### Tier 2 — Coherent Vertical Toolkit (visible in main nav / action menu)

| Feature | Description |
|---|---|
| Quote → Bill / Invoice | Turn a sent quotation into a GST invoice in one step |
| Quotation Comparison | Compare 2–10 supplier quotes side-by-side (decide vendor) |
| GST Validator | Sanity-check any invoice for HSN/math/format issues |
| Bill to Make (parse a supply list → invoice) | The existing feature, kept |
| Save / manage tender format templates | Library of saved "your formats" |

### Tier 3 — Utilities Drawer (hidden behind a "More tools" menu / `/tools`)

| Feature | Description |
|---|---|
| PDF ↔ DOCX, Excel → DOCX, Export to PDF | Conversions |
| Add watermark / Remove background | Image utilities |
| Product Catalog PDF | Single-page catalog from a photo |
| Rename file | Trivial helper |

> **Rule:** Utility features are never mentioned in onboarding, the homepage hero, or the
> first-time empty state. They're available, not advertised.

---

## 4. Workstreams Overview & Sequencing

| ID | Workstream | Channel | Effort | Depends on |
|---|---|---|---|---|
| WS-A | Unified identity, auth, channels table | Backend | 4d | — |
| WS-B | Output storage, retry, errors, counters | Backend | 3d | — |
| WS-C | Generic `/process/<feature>` API | Backend | 4d | WS-B |
| WS-D | Telegram bot completion + anchor reframe | Telegram | 5d | WS-B, WS-C |
| WS-E | WhatsApp bot channel (BSP-backed) | WhatsApp | 7d | WS-A, WS-C |
| WS-F | Web app scaffolding + auth | Web | 3d | WS-A |
| WS-G | Web app information architecture | Web | 2d | WS-F |
| WS-H | Web app anchor flow UX | Web | 6d | WS-F, WS-C |
| WS-I | Web app toolkit + utilities + history + settings | Web | 6d | WS-H |
| WS-J | Cross-channel QA + parity tests | All | 3d | All above |

Parallelization: WS-A/B can start immediately. WS-D, WS-F can start after WS-A. WS-C blocks
both bots and Web from final integration.

---

## 5. WS-A · Backend: Unified Identity, Auth & Channels

### Why

Today identity is `User.telegram_user_id`. That breaks the moment the same person uses the
Web or WhatsApp. We need one user, many channel handles.

### Schema changes (Alembic migration `004_unify_channels.py`)

```python
# New table
class ChannelLink(Base):
    __tablename__ = "channel_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)  # "telegram" | "whatsapp" | "web"
    handle: Mapped[str] = mapped_column(Text, nullable=False)   # telegram_user_id, e164, email
    verified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("channel", "handle", name="uq_channel_handle"),
    )
```

We **keep** `User.telegram_user_id` for backward compatibility but stop relying on it as
the only identity. The `channel_links` table is the new source of truth for "who is this
handle?"

### Auth modes

| Mode | Used by | Header |
|---|---|---|
| `X-Bot-Token` (existing shared secret) | Telegram bot, WhatsApp bot | `X-Bot-Token: <secret>` |
| `Authorization: Bearer <JWT>` (new) | Web app | `Authorization: Bearer ...` |

### Web auth flow (email OTP)

1. `POST /api/v1/auth/web/request-otp` → `{ email }` → API generates 6-digit OTP, stores
   hashed + expiring in Redis (`otp:<email>` TTL 10 min), sends email via Resend/SendGrid.
2. `POST /api/v1/auth/web/verify-otp` → `{ email, otp }` → API verifies → returns:
   ```json
   { "access_token": "...", "refresh_token": "...", "user": {...}, "organization": {...} }
   ```
3. JWT contains `sub` (user_id), `org_id`, `exp` (1h access / 30d refresh).
4. `POST /api/v1/auth/web/refresh` swaps refresh for new access token.

### Linking channels later

When a logged-in web user wants to also use Telegram:
- Web shows a deep link `https://t.me/<botname>?start=link_<token>` (token expires in 10 min, mapped to user_id in Redis).
- User opens Telegram → bot reads `start` payload → calls `POST /api/v1/channels/link` with `X-Bot-Token` + the linking token → creates a `ChannelLink` row.

Same pattern for WhatsApp (send a unique code to the WA number from the web; user replies with the code).

### Dependencies / library choices

- `python-jose[cryptography]` for JWT.
- `passlib[bcrypt]` (already implicit) for OTP hashing.
- Email: `resend` or `sendgrid` SDK; abstracted behind `app/core/email.py`.

### Acceptance

- A new test `tests/test_channel_link.py` confirms: register on Telegram → log in on Web with email → both handles resolve to the same `User` and same `Organization`.

---

## 6. WS-B · Backend: Output Storage, Retry, Errors, Counters

This is the foundation that prevents the silent-failure problem the original spec called
out. It does not need to be channel-specific — it lives in the API and processors.

### 6.1 Output storage (MinIO)

Move output upload **into the API service** so all channels benefit automatically.

```
outputs/{org_id}/{document_id}/{filename}
uploads/{org_id}/{document_id}/{original_filename}
```

The `processors` already produce a local file path. After processing, the API:
1. Uploads the input to `uploads/...`.
2. Uploads the output to `outputs/...`.
3. Writes a `Document` row with both keys.
4. Returns the document id, presigned download URL, and any structured metadata
   (`parsed_data`) to the caller (any channel).

### 6.2 Retry & error mapping

- Add `tenacity` retry on **external** calls inside the API:
  - OpenAI / LLM calls (3 attempts, exp backoff up to 5s).
  - MinIO/S3 ops (3 attempts).
- Replace **every** `except Exception: pass` in the bot with explicit logging + the
  decision rules in WS-D.
- Centralize user-facing copy in `app/core/error_messages.py` (the API). Channels receive
  a structured `ApiError { code, user_message, retryable, details }` and just display
  `user_message`.

```python
class ApiError(BaseModel):
    code: str           # E001 .. E010
    user_message: str   # human, channel-agnostic copy
    retryable: bool
    details: dict | None = None
```

Error codes (channel-neutral copy lives here):

| code | user_message |
|---|---|
| E001 | "We couldn't read all the data from your document. The format may be unusual." |
| E002 | "The AI couldn't understand the document. Try a clearer file or different format." |
| E003 | "The file appears to be empty or corrupted." |
| E004 | "You've used your monthly quota — upgrade to continue." |
| E005 | "We couldn't reach our server. Please try again in a moment." |
| E006 | "That file is too large. Maximum size is 15 MB." |
| E007 | "That file type isn't supported here." |
| E008 | "Processing took too long. Try a smaller file or split it." |
| E009 | "Something went wrong. Your file is still loaded — try another action." |
| E010 | "We couldn't open your saved format template. Please re-upload it." |

### 6.3 Counters (invoice / PO / quotation numbers)

Already partly done — `POST /api/v1/profile/.../increment-counter` exists for telegram_user_id.
Extend it to accept the JWT user as well (no body change).

---

## 7. WS-C · Backend: Generic "Process Document" API

This is the single endpoint every channel calls. It is the most important new API.

### Endpoint

```
POST /api/v1/process/{feature}
Authorization: Bearer <JWT>  (or X-Bot-Token + X-User-Id for bots)

Multipart body OR JSON:
- file: (file upload)  [for upload-based features]
- params: JSON         [feature-specific params]
- format_id: UUID      [optional, for sister quotation]
- mode: "preview"|"final"  [default "final"]
```

`{feature}` values:

| feature | Inputs | Output |
|---|---|---|
| `sister_quote` | file + format_id (or template_file) | DOCX/PDF + parsed JSON |
| `bill_to_make` | file + bill_no + bill_date + (HSN map) + (BillTo) | PDF + parsed JSON |
| `compare` | files[] (2..10) | DOCX |
| `gst_validate` | file | text report |
| `to_docx` | file | DOCX |
| `to_pdf` | file | PDF |
| `watermark` | file + mode + (text\|logo) | image |
| `bg_remove` | file | PNG |
| `catalog` | image + item details | PDF |
| `rename` | file + new_name | file |
| `create_quote` | (no file) JSON: customer + items + terms | DOCX |
| `create_invoice` | (no file) JSON: customer + items + GST | PDF |
| `create_po` | (no file) JSON | PDF |

### Response shape

```json
{
  "document_id": "uuid",
  "output_filename": "name.pdf",
  "output_url": "https://minio.../presigned",
  "input_url": "https://minio.../presigned",
  "parsed_data": { ... },               // when applicable (e.g., extracted items)
  "needs_confirmation": false,           // true if mode=preview returns extracted data
  "quota": { "used": 42, "limit": 100 }
}
```

### Preview vs Final modes

- `mode=preview` (web flow): runs only extraction/parsing. Returns `parsed_data` and
  `needs_confirmation: true`. **No** quota increment. **No** output file generated.
- `mode=final` (bot flow / confirmed web flow): runs the full render. Quota incremented.
  Output stored. Document row written.

This is what enables the "confirm before send" rule (Principle 5).

### Why this matters

It collapses 10+ ad-hoc endpoints into one consistent surface, and lets every channel use
identical request/response shapes.

---

## 8. WS-D · Telegram Bot: Completion & Reframe to Anchor

The existing bot is feature-complete but **wrongly framed** and has incomplete error
handling. This workstream fixes both.

### 8.1 Reframe: anchor first

- `/start` (registered): the first prompt is *"Send me a supplier quote (PDF/DOC/DOCX) — I'll convert it to your branded quote in seconds."* Not the 12-feature list.
- The main menu on `/menu` shows in this order:
  1. **Sister Quotation** (anchor)
  2. Quotation toolkit (compare, GST validate, quote→bill)
  3. `/tools` for utilities
  4. `/create` for from-scratch flows (deprioritized; only relevant when user has no input)
- Remove dead `format_keyboard()` (hardcoded SV/Sanmati/NR names).
- Fix `/upgrade` (currently a dead link).

### 8.2 Adopt the generic `/process` API

Refactor `bot.py` so every action calls `POST /api/v1/process/<feature>` instead of running
processors locally. The bot is now allowed to **not** import `processors.*` at all.

Migration steps for each feature:
1. Existing local processor call → replace with `api_client.process(feature, file, params)`.
2. Existing local upload to MinIO → removed (API handles it).
3. Existing local quota increment / log_document → removed (API handles it).

### 8.3 Implement remaining UX gaps (from PRODUCT_SPEC_V2)

Carry over from the previous spec, with these refinements aligned to the vertical:

- **State-aware fallback** for every `BotState` (table in §4 of `PRODUCT_SPEC_V2.md`).
- **Confirm-before-send** for sister quotation and bill-to-make: show extracted items in a
  small table, with `[✅ Looks good — generate]` and `[✏️ Edit]` buttons.
- **Progress messages** during LLM operations.
- **Soft reset** (preserve uploaded file on error).
- **File replacement confirmation** when a user uploads a new file mid-flow.

### 8.4 Health check & "what changed" message

When a returning user types `/start`, show a one-line "What's new" banner pointing to the
web app and WhatsApp.

### 8.5 Files to touch

- `services/bot-telegram/app/bot.py` — refactor all processing calls
- `services/bot-telegram/app/api_client.py` — add `process()`, drop direct MinIO use
- `services/bot-telegram/app/keyboards.py` — re-order anchor first; remove dead code
- `services/bot-telegram/app/handlers/onboarding.py` — new welcome copy

---

## 9. WS-E · WhatsApp Bot Channel

### 9.1 Provider choice

Use a **WhatsApp Business Solution Provider (BSP)** rather than direct Meta Cloud API at
MVP:

- **WATI** — easiest, India-friendly, ₹2,500/mo starter, webhook to our service.
- **Gupshup** — competitive pricing, India-based.
- **Meta Cloud API direct** — cheapest at scale but requires our own template approval
  and ops; defer to Phase 2.

Architect the channel so the BSP is swappable (interface below).

### 9.2 Service shape

```
services/bot-whatsapp/
├── app/
│   ├── main.py            ← FastAPI webhook server
│   ├── webhook.py         ← BSP webhook normalization
│   ├── bsp/
│   │   ├── base.py        ← Provider interface
│   │   ├── wati.py
│   │   └── gupshup.py
│   ├── conversation.py    ← State machine (similar to telegram bot.py)
│   ├── api_client.py      ← Same client as telegram (calls /process/<feature>)
│   ├── session_store.py   ← Redis-backed; key: docseva:wa:session:<e164>
│   └── messages.py        ← Channel-neutral copy lookup
```

### 9.3 Conversation model on WhatsApp

WhatsApp has constraints Telegram doesn't:
- No native inline-keyboard layout like Telegram's grid. Use **interactive list/button
  messages** (max 3 buttons, max 10 list items).
- **24-hour window** for free-form replies after the user messages; outside that, only
  approved **templates**.
- Media types: image, document, audio. Documents up to 100 MB on WhatsApp.

### 9.4 UX strategy

The conversation follows the same state machine as Telegram, but rendered as:

- **Interactive buttons** for short choice sets (≤3): main actions like
  `[📋 Sister Quotation] [📊 Compare] [More]`.
- **Interactive lists** for longer choice sets (≤10): saved format templates.
- **Free-text fallback**: user typing `1`, `2`, `3` or feature names also works.

### 9.5 Required pre-approved templates (Meta business templates)

| Name | Purpose | Variables |
|---|---|---|
| `docseva_welcome` | First-time greeting outside 24h window | name |
| `docseva_quote_ready` | Notify user their quote is ready (re-engagement) | filename |
| `docseva_quota_low` | Quota warning | used, limit |

Submit these for approval on day 1 of WS-E; approval takes 1–3 business days.

### 9.6 Identity & onboarding

- Webhook receives a message → lookup `ChannelLink` by `channel='whatsapp', handle=<e164>`.
- If not found → "Hi! Send your business name to get started." Same flow as Telegram
  onboarding, but with one fewer step (we already have their phone number from the
  channel).
- If user signed up via Web first and wants to link WhatsApp → web shows a one-time code;
  user WhatsApps that code to our number; we link.

### 9.7 Files / deliverables

- New service `bot-whatsapp` in `docker-compose.yml`.
- Public HTTPS webhook (nginx route `/whatsapp/webhook` → service).
- New schemas: `WhatsAppMessage`, `WhatsAppButtonReply`.
- New tests: `tests/test_wa_webhook.py`, `tests/test_wa_conversation.py`.

---

## 10. WS-F · Web App: Architecture & Stack

### 10.1 Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 14 (App Router)** | Server components + good SEO + India-friendly perf |
| Language | **TypeScript** | Type-safe API calls + maintainability |
| Styling | **Tailwind CSS** | Fast, consistent, no bespoke CSS |
| Components | **shadcn/ui** | Owned components, no vendor lock |
| Forms | **react-hook-form + zod** | Robust validation matching Pydantic schemas |
| Data fetching | **TanStack Query (React Query)** | Caching, retries, optimistic updates |
| Auth | **JWT** stored in httpOnly cookie | Safer than localStorage |
| File uploads | **direct multipart to API** | No middleman; supports presigned uploads later |
| Icons | **lucide-react** | Light, consistent |
| Dates | **date-fns** | Tree-shakable |
| PDFs in browser | **react-pdf** (preview only) | Inline preview of generated outputs |

### 10.2 Project layout

```
services/web/
├── app/
│   ├── (marketing)/         ← public landing/pricing
│   ├── (app)/               ← authenticated routes
│   │   ├── dashboard/
│   │   ├── new-quote/       ← anchor flow
│   │   ├── library/         ← formats + history
│   │   ├── tools/           ← Tier 3 utilities drawer
│   │   ├── settings/
│   │   └── layout.tsx       ← protected layout
│   ├── api/auth/[...]       ← Next.js route handlers (proxy to FastAPI)
│   └── layout.tsx
├── components/
│   ├── ui/                  ← shadcn primitives
│   ├── quote/               ← QuoteWizard, ItemsTable, ConfirmPanel
│   ├── shared/
│   └── forms/
├── lib/
│   ├── api.ts               ← Typed API client
│   ├── auth.ts              ← Session helpers
│   └── schemas.ts           ← Zod mirrors of Pydantic
├── hooks/
├── public/
└── package.json
```

### 10.3 Performance budgets

- LCP < 2.5s on a 3G connection (India 4G median is fine but assume tier-2 ground reality).
- Total JS shipped on landing < 150KB gzipped (use server components aggressively).
- All forms validate client-side before any API call.

### 10.4 Deployment

- Containerized; included in `docker-compose.yml`.
- Behind nginx (already proxying API). Add `/` → `web:3000`, `/api/` → `api:8000`.

---

## 11. WS-G · Web App: Information Architecture

### 11.1 Site map

```
Marketing (public)
├── /                       Landing — single-page, anchor-first
├── /pricing                Two-tier pricing
├── /privacy, /terms
└── /login                  Email OTP

App (authenticated)
├── /dashboard              First-screen-after-login
├── /new-quote              ← THE anchor flow (most important page)
├── /library
│   ├── /library/formats    Tender format templates
│   └── /library/history    Past quotes/invoices/PDFs
├── /tools                  Utilities drawer (Tier 3)
│   ├── /tools/compare
│   ├── /tools/gst-validate
│   ├── /tools/convert
│   ├── /tools/watermark
│   ├── /tools/bg-remove
│   └── /tools/catalog
├── /settings
│   ├── /settings/profile   Company name, address, GSTIN
│   ├── /settings/branding  Logo upload
│   ├── /settings/bank      Bank details
│   ├── /settings/numbering Invoice/PO/Quote prefixes
│   ├── /settings/team      (Phase 2)
│   └── /settings/channels  Link Telegram/WhatsApp
└── /billing                Plan & upgrade
```

### 11.2 Navigation

- Persistent **left sidebar** (collapses on mobile) with: Dashboard, New Quote, Library,
  Tools, Settings.
- Top bar with org name, quota indicator (e.g., `42 / 100 docs`), avatar.
- **Anchor CTA is always one click away**: a sticky `[+ New Quote]` button in the sidebar.

### 11.3 First-run experience (the part that makes it self-explanatory)

When a brand-new user logs in for the first time, the dashboard shows a one-screen
**Setup Wizard**, not a feature list:

```
┌──────────────────────────────────────────────────────┐
│  Welcome to DocSeva 👋                                │
│                                                        │
│  Let's set you up in 60 seconds.                      │
│                                                        │
│  [1/3] Company details       [▣]                      │
│        Name, address, GSTIN                            │
│                                                        │
│  [2/3] Upload your logo      [○]                      │
│        Appears on every quote                          │
│                                                        │
│  [3/3] Upload one tender     [○]                      │
│        format template (PDF/DOCX) you usually use      │
│                                                        │
│  [ Skip and try the demo →]                            │
└──────────────────────────────────────────────────────┘
```

After completion, route to `/new-quote` automatically. **The user lands at the anchor.**

### 11.4 Dashboard (returning users)

- Top: greeting + quota.
- **Big primary card**: "Convert a supplier quote → your branded quote" with one button.
- **Recent activity** (5 items) from the document history.
- **Smaller secondary cards**: "Compare quotations", "Validate GST", "Tools".
- No 12-feature grid.

---

## 12. WS-H · Web App: Anchor Flow UX

This is the most important screen in the entire app. Detailed below.

### 12.1 The 4-step wizard at `/new-quote`

**Step 1 — Drop a supplier quote**

```
┌─────────────────────────────────────────────────────┐
│   Step 1 of 4 · Drop your supplier's quote          │
│                                                       │
│   ┌─────────────────────────────────────────────┐  │
│   │                                               │  │
│   │           Drag a file here or click           │  │
│   │           to browse (PDF / DOC / DOCX)        │  │
│   │                                               │  │
│   │           Or paste items as text below 👇     │  │
│   └─────────────────────────────────────────────┘  │
│                                                       │
│   [ Or type items manually instead ]                │
│                                                       │
│                                  [ Continue → ]      │
└─────────────────────────────────────────────────────┘
```

- Single drop zone. Single CTA. No competing actions.
- Manual entry path (typed list) coexists for users without a file.

**Step 2 — Confirm what we extracted**

```
┌─────────────────────────────────────────────────────┐
│   Step 2 of 4 · Confirm the extracted items          │
│                                                       │
│   We read this from your file:                       │
│                                                       │
│   ┌─ Customer (Bill To) ──────────────────────────┐ │
│   │ Name:    [ABC Lab Pvt Ltd          ] [edit]   │ │
│   │ Address: [12 MG Road, Delhi        ] [edit]   │ │
│   │ GSTIN:   [07ABCDE1234F1Z5          ] [edit]   │ │
│   └────────────────────────────────────────────────┘ │
│                                                       │
│   ┌─ Items ────────────────────────────────────────┐ │
│   │ #  Name              Qty  Price    HSN  [x]    │ │
│   │ 1  pH Meter PHM-501  2    12,000   9027 [✏][🗑]│ │
│   │ 2  Digital Therm     5    4,500    9025 [✏][🗑]│ │
│   │ + Add item                                      │ │
│   └────────────────────────────────────────────────┘ │
│                                                       │
│   ⚠️  2 items have no HSN — fill or skip             │
│                                                       │
│           [ ← Back ]              [ Continue → ]     │
└─────────────────────────────────────────────────────┘
```

This is the **mandatory confirmation step.** Every cell editable inline. Validation
errors shown inline. The user owns the data before it goes into a PDF.

**Step 3 — Pick your output format**

```
┌─────────────────────────────────────────────────────┐
│   Step 3 of 4 · Choose your output format            │
│                                                       │
│   Saved formats:                                      │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│   │ ✓ My Default │ │ Tender Form  │ │ Govt Lab     ││
│   │   (selected) │ │              │ │              ││
│   │              │ │              │ │              ││
│   │ [thumbnail]  │ │ [thumbnail]  │ │ [thumbnail]  ││
│   └──────────────┘ └──────────────┘ └──────────────┘│
│                                                       │
│   [ + Upload a new format ]                          │
│                                                       │
│   Output type: ( ) DOCX   (•) PDF                    │
│                                                       │
│   Optional: adjust prices by   [ +0% ▼]              │
│                                                       │
│           [ ← Back ]            [ Generate → ]       │
└─────────────────────────────────────────────────────┘
```

**Step 4 — Done**

```
┌─────────────────────────────────────────────────────┐
│   ✅ Your branded quote is ready                      │
│                                                       │
│   [Inline PDF preview iframe]                         │
│                                                       │
│   [ ⬇ Download ]  [ 📤 Share via WhatsApp ]          │
│   [ 📧 Email ]    [ ✏ Make changes ]                 │
│                                                       │
│   What next?                                          │
│   [ Convert to invoice ]  [ Make another quote ]     │
└─────────────────────────────────────────────────────┘
```

- "Share via WhatsApp" generates a `https://wa.me/?text=...` link pre-filled with the
  presigned URL.
- "Make changes" re-opens Step 2 with the saved parsed_data — no re-upload, no re-parse.

### 12.2 State management

The wizard uses a single React Hook Form + Zustand store (`useNewQuoteStore`) so users
can flip back/forward without losing data.

### 12.3 Edge cases (all must be designed)

| Case | Behavior |
|---|---|
| LLM fails to parse | Show Step 2 with an empty table + clear inline error: "We couldn't read items — add them manually." User can still proceed. |
| File > 15 MB | Reject at drop-zone with toast. |
| Quota exhausted | Block "Generate" with an inline upgrade banner; everything else still works. |
| User leaves mid-flow | On return to `/new-quote`, show a "Resume your last draft?" prompt (draft saved in `documents` with `status='draft'`). |
| User has no saved formats | Step 3 shows a built-in default + uploader; never blocks. |

---

## 13. WS-I · Web App: Other Screens

### 13.1 Library

- **`/library/formats`** — grid of saved tender format templates with thumbnails (rendered server-side from the first page of the DOCX/PDF), upload + delete.
- **`/library/history`** — table of all generated docs with filters: feature, date range, status. Each row links to a detail page with inline preview + "Edit" (regenerate with new params).

### 13.2 Tools (`/tools`)

- A single page with cards for: Compare, GST Validate, Convert (PDF↔DOCX/Excel), Watermark, Background Remove, Product Catalog, Rename.
- Each card → its own sub-page with a focused single-action UI.
- This is **the utilities drawer** — accessible, but never the homepage hero.

### 13.3 Settings

- **Profile**: name, address, city, state, pincode, GSTIN, PAN, phone, email, website.
- **Branding**: upload logo + preview on a sample quote.
- **Bank**: bank name, account number, IFSC.
- **Numbering**: prefixes and counters for invoice/PO/quotation.
- **Channels**: link/unlink Telegram and WhatsApp (deep link / verification code).
- **Team**: invite by email (Phase 2).

### 13.4 Billing

- Plan card with current usage.
- Upgrade buttons (Razorpay integration — Phase 2; Phase 1 = "Contact us" CTA).

---

## 14. WS-J · Cross-Channel Parity Matrix

Every feature must work on every channel that is sensible for it.

| Feature | Web | Telegram | WhatsApp |
|---|---|---|---|
| Sign up / log in | ✅ Email OTP | ✅ Auto (TG id) | ✅ Auto (E164) |
| Onboarding | ✅ Wizard | ✅ Conversational | ✅ Conversational |
| Sister Quotation (anchor) | ✅ Wizard | ✅ Chat flow | ✅ Chat flow |
| Confirm extracted items | ✅ Editable table | ✅ Text summary + ✏️ buttons | ✅ Same |
| Pick output format | ✅ Card grid | ✅ Inline keyboard | ✅ List msg |
| Price adjustment | ✅ Inline select | ✅ ✅ | ✅ ✅ |
| Bill to Make | ✅ Wizard | ✅ | ✅ |
| Comparison (2–10 files) | ✅ Multi-upload | ✅ Sequential | ✅ Sequential |
| GST Validator | ✅ Single file | ✅ | ✅ |
| Quote → Bill | ✅ One-click | ✅ Button | ✅ Button |
| Create from scratch (invoice/quote/PO) | ✅ Wizard | ✅ Long flow | ⚠️ Long flow — discourage on WA, link to web |
| Utilities (watermark/bgremove/etc.) | ✅ `/tools` | ✅ Action menu | ✅ Action menu |
| Library / History | ✅ Rich table | ✅ `/history` text | ✅ `/history` text |
| Edit generated doc | ✅ Step 2 reopen | ✅ Edit menu | ✅ Edit menu |
| Settings | ✅ Full | ✅ `/settings` (basic) | ✅ `/settings` (basic) |
| Channel linking | ✅ Initiate | ✅ Accept deep link | ✅ Accept code |

> **Rule:** if a feature requires more than ~5 conversational steps, bots route the user
> to the web app for it ("This works best on the web — open: https://docseva.in/new-quote").
> Don't punish dealers by forcing a 15-step chat.

---

## 15. Data Model Changes

Consolidating across all workstreams (Alembic migration `004_multichannel.py`):

### New tables

```python
class ChannelLink(Base):
    __tablename__ = "channel_links"
    # (see §5)

class WebSession(Base):
    """Refresh tokens; access tokens are stateless JWT."""
    __tablename__ = "web_sessions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    revoked_at: Mapped[datetime | None]

class Draft(Base):
    """Persisted in-progress wizards (web) and unfinished chat flows (bots)."""
    __tablename__ = "drafts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(Text)            # web|telegram|whatsapp
    feature: Mapped[str] = mapped_column(Text)             # sister_quote, bill_to_make...
    state: Mapped[dict] = mapped_column(JSONB, default=dict)
    expires_at: Mapped[datetime]
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

### Column additions

- `documents.input_file_key TEXT NULL`
- `documents.source_document_id UUID NULL REFERENCES documents(id) ON DELETE SET NULL`
- `documents.document_type TEXT NULL` ("quote", "invoice", "po", "sister_quote", ...)
- `documents.parsed_data JSONB` (move from generic `metadata`; old field stays)
- `users.email TEXT UNIQUE NULL` (web auth uses this)
- `company_profiles.po_prefix`, `po_counter`, `quotation_prefix`, `quotation_counter`
  (already done per WS-3 in PRODUCT_SPEC_V2 — keep)

---

## 16. API Contract Additions

Beyond `/process/<feature>` (WS-C), we add:

### Auth (Web)

| Method | Path | Body |
|---|---|---|
| POST | `/api/v1/auth/web/request-otp` | `{ email }` |
| POST | `/api/v1/auth/web/verify-otp` | `{ email, otp }` → tokens |
| POST | `/api/v1/auth/web/refresh` | `{ refresh_token }` |
| POST | `/api/v1/auth/web/logout` | (revoke refresh) |
| GET | `/api/v1/auth/me` | current user + org + profile |

### Channels

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/channels` | list linked channels |
| POST | `/api/v1/channels/link` | bot → API with linking token to create link |
| POST | `/api/v1/channels/web/start-link` | web → returns linking token + deep link |
| DELETE | `/api/v1/channels/{id}` | unlink |

### Drafts

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/drafts?feature=sister_quote` | list user's open drafts |
| POST | `/api/v1/drafts` | create/replace |
| GET | `/api/v1/drafts/{id}` | fetch one |
| DELETE | `/api/v1/drafts/{id}` | discard |

### Documents

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/documents/{id}/download` | 302 to presigned URL |
| GET | `/api/v1/documents/{id}/metadata` | parsed_data for editing |
| POST | `/api/v1/documents/{id}/regenerate` | re-render from edited parsed_data |

### Backward compatibility

The existing `/api/v1/documents/{telegram_user_id}` style endpoints stay — they remain the
bots' interface. The web app uses ID-based equivalents authenticated by JWT.

---

## 17. Design System & UX Standards

### 17.1 Typography & spacing (web)

- Headings: Inter / IBM Plex Sans, weights 600/700.
- Body: 16px base, 1.5 line-height.
- Container max-width 1200px on dashboard, 720px on wizards (focused flows).

### 17.2 Color tokens

- Primary action: indigo-600. Hover: indigo-700.
- Success: emerald-600. Warning: amber-500. Danger: rose-600.
- All comply with WCAG AA contrast.

### 17.3 Components (shadcn)

`Button`, `Input`, `Label`, `Card`, `Dialog`, `Sheet`, `Table`, `Toast`, `Tooltip`,
`Dropdown`, `Tabs`, `Select`, `Combobox`, `Skeleton`, `Progress`.

### 17.4 Tone of voice (everywhere — web copy + bot messages)

- Plain Indian English; one short sentence per idea.
- Never expose Python exceptions. Always say what the user can do next.
- "We" (the product) helps "you" (the dealer). No corporate jargon.
- Action button labels are verbs: "Generate quote", "Edit items", not "Submit".

### 17.5 Accessibility

- All form controls labelled.
- Keyboard navigation across the entire wizard.
- Focus rings visible.
- ARIA live regions on progress/status messages.

### 17.6 Mobile

- Wizard collapses to single-column on < 640px.
- Drop zone supports `capture="filesystem"` only — many users will be on phones.
- Bottom action bar (sticky) on mobile keeps `[Continue]` always reachable.

---

## 18. Observability, Security, Compliance

### 18.1 Logging

- Structured JSON logs on all services (`structlog`).
- Every request: `user_id`, `org_id`, `channel`, `feature`, `request_id`.
- Every LLM call: token counts, latency, retries.

### 18.2 Metrics

- Prometheus client in API service. Key counters:
  - `documents_generated_total{feature,channel,status}`
  - `llm_calls_total{model,outcome}`
  - `quota_exhausted_total{plan}`
  - `auth_events_total{type,outcome}`
- Plus latency histograms per feature.

### 18.3 Error tracking

- Sentry (or self-hosted GlitchTip) integrated in API + web.

### 18.4 Security

- JWT secret rotation supported (key id in header).
- httpOnly + Secure + SameSite=Lax cookies for refresh tokens.
- Rate limit `request-otp` (5/min/email) and `verify-otp` (10/min/IP).
- Presigned URLs expire in 24h max.
- File-type sniffing on every upload (don't trust extensions).
- CSRF protection on the web app (Next.js middleware + sameSite + double-submit cookie if needed).
- `helmet`-style security headers via Next.js config.

### 18.5 Compliance

- DPDP Act readiness:
  - Document retention configurable (already exists: `DOCUMENT_RETENTION_DAYS`).
  - Add `POST /api/v1/account/export-data` (zip of user's docs + JSON).
  - Add `DELETE /api/v1/account` (full org wipe).
- Terms & Privacy pages on web (`/terms`, `/privacy`).

---

## 19. Testing Strategy

| Layer | Tool | Scope |
|---|---|---|
| Backend unit | pytest | Processors, parsers, error mapping, retry |
| Backend integration | pytest + httpx test client | `/process/<feature>` end-to-end, auth, channel linking |
| Bot (telegram) | pytest with mocked Update | State transitions, callbacks |
| Bot (whatsapp) | pytest with mocked BSP webhooks | Webhook normalization, state |
| Web unit | vitest | Components, hooks, validation schemas |
| Web E2E | **Playwright** | Anchor flow (sign up → upload → confirm → generate → download) on Chromium + WebKit + mobile viewport |
| Visual regression | Playwright snapshots | Landing, dashboard, wizard |
| Load | k6 | `/process/sister_quote` to validate concurrency assumptions |

### Cross-channel parity test (the critical one)

A test that for the same input file + format, the SHA-1 (or layout-equivalence) of the
output PDF generated through:
- Web `/process` API call
- Telegram bot call to `/process`
- WhatsApp bot call to `/process`

...is identical. This proves the "one brain, many faces" principle is actually true.

---

## 20. Release Plan & Sprint Breakdown

Each sprint = 1 calendar week. Adjust to your team size.

### Sprint 1 — Foundation (Backend)

- WS-A: identity, channel links, JWT auth, email OTP.
- WS-B: output storage in API, retry, error mapping, structured logs.
- Migration `004_multichannel.py`.
- Cross-team API contract freeze for `/process/<feature>` (WS-C scaffolding only).

### Sprint 2 — Backend brain + Telegram refactor

- WS-C: implement `/process/<feature>` for every existing feature (move processors into API).
- WS-D: refactor Telegram bot to call `/process/<feature>`; reframe to anchor-first;
  fix dead `/upgrade`, dead `format_keyboard`.
- Backward-compat tests pass — existing Telegram users see no regression.

### Sprint 3 — Web app shell + Anchor flow

- WS-F: Next.js scaffold, login (email OTP), dashboard skeleton, setup wizard.
- WS-G: full IA + routing in place.
- WS-H: `/new-quote` 4-step wizard implemented end-to-end (Tier 1 anchor only).

### Sprint 4 — Web app: rest of the surface

- WS-I: Library (formats + history), Tools drawer, full settings, billing CTA.
- Polish + accessibility audit.
- Playwright suite green on Chromium + mobile.

### Sprint 5 — WhatsApp channel

- WS-E: BSP integration (WATI first), webhook + conversation, template approval submitted on Day 1.
- Channel linking flows from Web and Telegram.
- Parity test passes across all 3 channels.

### Sprint 6 — Hardening, launch

- WS-J: full parity + load tests.
- Security review (auth, file upload, presigned URLs).
- DPDP readiness (data export + account delete).
- Soft launch to 20 dealers from Sanmati network (already validated audience).
- Gather metrics for 1 week → iterate.

> **Total: 6 weeks.** Achievable with one backend engineer, one frontend engineer, one
> bot/devops engineer. Tighter is possible with overlap; looser is safer.

---

## 21. Definition of Done

A workstream is "done" only when all of these are true:

1. Code merged to main with passing CI.
2. Unit + integration tests added; coverage ≥ 80% on new code.
3. No `except Exception: pass` introduced. All errors map to `ApiError` codes.
4. User-facing copy reviewed against tone of voice rules (§17.4).
5. At least one E2E test exercises the new path.
6. Docs updated: README + this file + OpenAPI schema regenerated.
7. Deployed to staging; smoke-tested by a non-author engineer.

---

## Appendix A — Anchor Flow Wireframe (Web)

See §12.1 for the four-step text wireframes. Designer deliverables required:

- High-fidelity mock of Step 1 (drop zone + manual entry tab).
- High-fidelity mock of Step 2 (editable table with HSN warning state, empty state, LLM-failed state).
- High-fidelity mock of Step 3 (format cards with thumbnails).
- High-fidelity mock of Step 4 (success + share + next actions).
- Mobile breakpoints for all four.
- Empty state for `/library/history`.
- Setup wizard (first-run dashboard).

---

## Appendix B — Telegram/WhatsApp Anchor Scripts

### Telegram (post-reframe)

```
USER: /start  (registered)
BOT:  👋 Welcome back, *Sanmati Enterprises*.

      📎 Drop your supplier's quote — I'll turn it into your branded
      customer quote in seconds.

      Or type /tools for utilities.
───────────────────────────────────────
USER: (sends quote.pdf)
BOT:  📂 *quote.pdf* received.

      [📋 Sister Quotation]   ← anchor, first
      [📊 Compare quotations]
      [🧮 Validate GST]
      [🧾 Bill to Make]
      [More ▾]                ← collapses tier-3 + utilities
───────────────────────────────────────
USER taps: 📋 Sister Quotation
BOT:  ⏳ Reading your file... (1/3)
      🤖 Extracting items... (2/3)
      📐 Preparing preview... (3/3)
───────────────────────────────────────
BOT:  Here's what I read — please confirm:

      *Bill To:* ABC Lab Pvt Ltd
      *Items (2):*
      1. pH Meter PHM-501  ×2 @ ₹12,000
      2. Digital Therm     ×5 @ ₹4,500

      [✅ Looks good — pick format]
      [✏️ Edit items]
      [❌ Cancel]
───────────────────────────────────────
USER taps: ✅ Looks good
BOT:  Pick your output format:
      [My Default]  [Tender Format]  [Govt Lab]
      [+ Upload new]
───────────────────────────────────────
USER taps: Tender Format
BOT:  ⚙️ Generating your branded quote...
BOT:  [📄 ABC_Lab_quote.docx]
      ✅ Done. Saved to your Library.
      [📤 Forward this] [✏️ Edit] [➕ New quote]
```

### WhatsApp (same logic, fewer buttons per message)

```
USER: (sends quote.pdf to the DocSeva WA number)
BOT:  📂 Got it — quote.pdf.

      What do you want me to do?

      [Sister Quotation]
      [Validate GST]
      [More ▾]
───────────────────────────────────────
USER taps: Sister Quotation
BOT:  ⏳ Reading...
BOT:  ⏳ Extracting items...
───────────────────────────────────────
BOT:  Here's what I read:

      Bill To: ABC Lab Pvt Ltd
      Items: 2 (pH Meter ×2 @ ₹12k, Therm ×5 @ ₹4.5k)

      Reply ✅ to confirm, or ✏️ to edit.
───────────────────────────────────────
USER: ✅
BOT:  Pick a format:
      1. My Default
      2. Tender Format
      3. Govt Lab
      (reply with the number)
───────────────────────────────────────
USER: 2
BOT:  ⚙️ Generating...
BOT:  [📄 ABC_Lab_quote.docx attached]
      Done. Want to send another? Just drop another file.
```

---

*End of plan — Multi-Channel Execution. Version 1.0 — 1 June 2026.*
