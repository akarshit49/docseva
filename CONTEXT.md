# DocSeva — Full Project Context & Roadmap

> **Read this first if you are a new agent or developer picking up this project.**
> This document captures the complete history, decisions, architecture, and roadmap for DocSeva.

---

## 1. Origin Story

DocSeva was cloned from a private Telegram bot originally built for **Sanmati Enterprises** (a scientific instruments trading company in Roorkee, Uttarakhand). That original bot — called `quotation-agent` — is located at:

```
/Users/Akarshit.jain/Desktop/AI Project/quotation-agent/
```

The original bot was single-tenant (hardcoded to Sanmati), had no database, and ran locally. After building out many features, the decision was made to generalize it into a multi-tenant SaaS product called **DocSeva** ("Doc" = documents, "Seva" = service in Hindi).

---

## 2. Original Bot Features (All Ported to DocSeva)

All of these features were built and tested in the original `quotation-agent` project and are now available in DocSeva's bot service:

### Document Features
| Feature | Input | Output | Description |
|---------|-------|--------|-------------|
| **Sister Quotation** | DOC/DOCX/PDF | DOCX | Re-formats a competitor's quotation into your own style. Uses LLM to parse, then renders in one of 3 DOCX templates. |
| **Price Adjustment** | (follow-up after Sister Quotation) | DOCX | After generating a sister quotation, user can increase/decrease all item prices by ~N% with humanized rounding (randomized ±2.5%, rounds to natural numbers). |
| **Bill to Make** | DOC/DOCX | PDF Invoice | Extracts table data (items, qty, price, GST) from a Word doc using LLM, then generates a professional invoice PDF with the user's company branding. |
| **PDF → DOCX** | PDF | DOCX | Reads PDF using `pdfplumber`, preserves tables and layout in output DOCX. |
| **Excel → DOCX** | XLS/XLSX | DOCX | Converts Excel sheets to DOCX with black-bordered table formatting. |
| **Export to PDF** | DOC/DOCX/XLS/XLSX | PDF | Pure Python conversion using `fpdf2`. No LibreOffice needed. |
| **Rename File** | Any | Same format | Returns file with a new name in the original format. |
| **GST Invoice Validator** | Any invoice file | Text report | Uses LLM to extract GST data, checks math correctness, validates HSN codes, flags errors. |
| **Quotation Comparison** | 2–5 quotation files | DOCX table | Sends multiple quotations one by one, get a side-by-side comparison table with lowest price highlighted and AI notes. |

### Image Features
| Feature | Input | Output | Description |
|---------|-------|--------|-------------|
| **Add Watermark** | PNG/JPG/HEIC etc. | Same format | Adds company logo as translucent (30% opacity) centered watermark. |
| **Remove Background** | PNG/JPG/HEIC etc. | PNG | AI-powered background removal using `rembg` (u2net model). |
| **Product Catalog PDF** | Image + text | PDF | Generates a professional single-page product catalog. User sends image, then types: `Item Name | Description | Price`. |

### Bot Commands
| Command | Description |
|---------|-------------|
| `/start` | Register or resume session |
| `/menu` | Show quota and status |
| `/settings` | Update company profile (name, GSTIN, logo, bank details) |
| `/history` | Last 10 processed documents |
| `/help` | Full feature overview |
| `/stop` | End current session |

---

## 3. Technical Decisions Made (with reasons)

### Why Python (not Node/Go)?
All document processing libraries (`pdfplumber`, `python-docx`, `fpdf2`, `rembg`, `openpyxl`) are Python-first. Switching would mean rewriting all converters.

### Why no LibreOffice?
LibreOffice was initially used for `.doc` → text extraction and DOCX → PDF. It was removed because:
- Not reliably available on all systems
- Requires a display server on Linux
- Pure Python alternatives (`olefile` for `.doc`, `fpdf2` for PDF) work well enough

### Why OpenAI (not Claude/Gemini)?
`gpt-4o-mini` is the cheapest capable model for structured JSON extraction. The prompts return strict JSON schemas. Claude or Gemini can be swapped in later — all LLM calls are in `processors/llm_parser.py`, `bill_to_make.py`, `gst_validator.py`, `quotation_compare.py`.

### Why MinIO (not AWS S3)?
MinIO is S3-compatible, self-hostable, and free. The boto3 client code is identical — you can swap `MINIO_ENDPOINT` to an S3 endpoint and it works on AWS S3 with zero code changes.

### Why FastAPI (not Django/Flask)?
FastAPI gives async support, automatic OpenAPI docs (`/docs`), Pydantic validation, and is much faster than Flask. SQLAlchemy 2.0 async works natively with it.

### Why Celery was NOT included (yet)?
For the Month 1 MVP, document processing happens inline inside the bot service (synchronous). This is simpler and works for low-to-medium load. Celery + Redis task queue will be added in Month 2 when we need background processing for WhatsApp and web dashboard uploads.

### Auth approach for MVP:
Telegram user ID is the identity. No OTP/JWT needed for the Telegram bot (Telegram itself verifies identity). Email/OTP will be added in Month 2 for the web dashboard login.

---

## 4. Current Architecture

```
Telegram ──► Bot Service (Python/python-telegram-bot)
                │  
                │ REST API calls (X-Bot-Token header)
                ▼
             API Service (FastAPI + SQLAlchemy 2.0 async)
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
    PostgreSQL Redis  MinIO
    (data)  (cache) (files)
```

### Service Locations
```
DocSeva/
├── services/
│   ├── api/                   # FastAPI backend
│   │   ├── app/core/          # Config, DB engine, MinIO client, security
│   │   ├── app/models/        # SQLAlchemy ORM models
│   │   ├── app/schemas/       # Pydantic request/response schemas
│   │   ├── app/routes/        # auth.py, profile.py, documents.py, health.py
│   │   └── alembic/           # DB migrations
│   │
│   └── bot/                   # Telegram bot
│       └── app/
│           ├── processors/    # All document & image converters
│           ├── handlers/      # onboarding.py (new user flow)
│           ├── api_client.py  # HTTP client → API service
│           ├── bot.py         # Main bot logic (state machine)
│           ├── keyboards.py   # All InlineKeyboard definitions
│           └── session_store.py  # BotState enum + UserSession dataclass
│
├── assets/                    # logo.png (default, bundled into bot Docker image)
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env                       # Real secrets (git-ignored)
├── .env.example               # Template
├── Makefile                   # make up / make logs / make migrate etc.
└── README.md
```

### Database Tables
| Table | Purpose |
|-------|---------|
| `organizations` | One row per company. Holds plan, quota counters. |
| `users` | One row per person. Linked to org. Holds telegram_user_id. |
| `company_profiles` | One row per org. Company name, address, GSTIN, logo key, bank details. |
| `documents` | Every processed file logged here (feature, filenames, MinIO key, created_at). |
| `usage_events` | Append-only log of every action (for future analytics). |

---

## 5. How the Bot Talks to the API

The bot sends a shared secret token in every request:
```
X-Bot-Token: <value of API_BOT_TOKEN in .env>
```
This is a simple shared-secret approach. It will be replaced with proper JWT in Month 2 when the web dashboard needs user-specific tokens.

### Typical flow for a document:
1. User sends file on Telegram
2. Bot downloads file to `/tmp/docseva/`
3. Bot calls `GET /api/v1/auth/quota/{telegram_id}` — checks if user has quota remaining
4. Bot processes the document locally (all converters run inside the bot container)
5. Bot calls `POST /api/v1/auth/quota/{telegram_id}/increment` — consumes 1 quota
6. Bot calls `POST /api/v1/documents/{telegram_id}` — logs the document to DB
7. Bot sends the output file back to user on Telegram

---

## 6. Multi-Tenancy: How Company Profile is Injected

The old project had hardcoded constants (CO_NAME = "SANMATI ENTERPRISES", etc.). DocSeva replaces these with dynamic profile injection.

**Before processing any document**, the bot calls:
```
GET /api/v1/profile/{telegram_id}
```
Which returns the user's company profile dict. This is passed into every processor function as a `company_profile` parameter.

Processors that use company profile:
- `renderers.py` — injects company name and footer into DOCX headers/footers
- `bill_to_make.py` — injects company name, address, GSTIN, bank details into invoice PDF
- `catalog_pdf.py` — injects company name and contact into catalog header/footer

---

## 7. Environment Variables (Key Ones)

| Variable | Where used | Notes |
|----------|-----------|-------|
| `TELEGRAM_BOT_TOKEN` | Bot service | From BotFather |
| `OPENAI_API_KEY` | Bot service | For LLM features |
| `OPENAI_MODEL` | Bot service | Default: `gpt-4o-mini` |
| `API_BOT_TOKEN` | Both services | Shared secret — change in production |
| `POSTGRES_PASSWORD` | Both services | Change in production |
| `MINIO_SECRET_KEY` | Both services | Change in production |
| `FREE_PLAN_DOCS_PER_MONTH` | API service | Default: 10 |

---

## 8. Running Locally

```bash
# 1. Make sure Docker Desktop is running
# 2. Navigate to project
cd /Users/Akarshit.jain/Desktop/DocSeva

# 3. Start everything
docker compose up -d

# 4. Watch bot logs
docker compose logs -f bot

# 5. Open API docs
open http://localhost:8000/docs

# 6. Open MinIO console
open http://localhost:9001
# Login: minioadmin / minioadmin_secret_change_in_prod
```

Useful Makefile shortcuts:
```bash
make up        # start all services
make down      # stop all services
make logs      # tail all logs
make bot-logs  # tail bot only
make api-logs  # tail api only
make migrate   # re-run migrations
make reset-db  # ⚠️ wipe and recreate DB (dev only)
```

---

## 9. Known Issues / Tech Debt

1. **`BucketAlreadyOwnedByYou` warning on API startup** — Two uvicorn workers both try to create MinIO buckets on startup. Second one gets this warning. Harmless but should be fixed by checking bucket existence before creating.

2. **In-memory session store** — Bot uses Python dict in memory (`session_store.py`). If bot restarts, all active conversations reset. Fix: move session store to Redis (already in the stack).

3. **Synchronous document processing** — All file processing blocks the bot's async event loop via `run_in_executor`. Works fine for 1-10 concurrent users. For production scale, move to Celery workers.

4. **No retry logic** — If API is temporarily down, bot API calls fail silently. Add `tenacity` retry decorator around all `api_client.py` calls.

5. **`version` attribute in docker-compose.yml** — Gets a deprecation warning from newer Docker Compose. Remove the `version: "3.9"` line.

6. **Bot container build context** — The bot Dockerfile uses the project root as build context (to copy `assets/`). This means any change in `services/bot/` requires rebuilding from root context. Consider a `.dockerignore` to speed up builds.

---

## 10. Roadmap

### ✅ Month 1 — COMPLETED (MVP Foundation)
- [x] Multi-tenant architecture (PostgreSQL + MinIO)
- [x] FastAPI backend with auth, profile, document logging
- [x] Alembic migrations
- [x] Docker Compose (local dev + production overrides)
- [x] Telegram bot — all original features ported
- [x] Multi-tenant bot: onboarding flow, company profile, quota
- [x] Dynamic company branding in all document outputs
- [x] Document history tracking

---

### 🔲 Month 2 — Web Dashboard + WhatsApp + Payments

#### Web Dashboard (Highest Priority)
- Stack: **Next.js 14** (App Router) + **Tailwind CSS** + **shadcn/ui**
- Backend: Same FastAPI API (add JWT auth for web users)
- Features for dashboard:
  - Login with email + OTP (send via Resend/SendGrid)
  - Upload files and select action (same as bot but in a nice web UI)
  - Document history table with download links
  - Company profile settings page (upload logo, fill GSTIN etc.)
  - Usage dashboard (quota used, plan, upgrade CTA)
  - Billing page (Razorpay integration)
- Create `services/dashboard/` directory with Next.js app
- Add `dashboard` service to `docker-compose.yml`
- Add JWT auth to API: `POST /api/v1/auth/login` (email + OTP), `POST /api/v1/auth/token` (verify OTP → JWT)
- Add `Authorization: Bearer <JWT>` support to all API routes (alongside X-Bot-Token)

#### WhatsApp Integration
- Use **WATI** or **Gupshup** as the WhatsApp Business API intermediary (Meta compliance handled by them)
- Create `services/whatsapp/` — a FastAPI webhook server
- WATI/Gupshup sends webhooks to our server when a user messages
- Bot logic is the same — just a different "channel" instead of Telegram
- Add `channel` field to `usage_events` table (already has it: default = "telegram")
- Cost: WATI starts at ~₹2,500/month

#### Payment Integration (Razorpay)
- Add `subscriptions` table to database
- Create `/api/v1/billing/` routes
- Razorpay webhook handler for payment confirmation
- Auto-upgrade org plan on successful payment
- Plans:
  - Free: 10 docs/month (already working)
  - Starter ₹499/mo: 100 docs/month
  - Pro ₹1,499/mo: 500 docs/month
  - Business ₹3,999/mo: Unlimited

#### Session Store → Redis
- Replace `SessionStore` dict in `session_store.py` with Redis-backed store
- Key: `session:{telegram_user_id}`, Value: JSON-serialized `UserSession`
- TTL: 24 hours
- Library: `redis-py` (already in requirements)

---

### 🔲 Month 3 — New Features

#### Purchase Order Generator
- User uploads a quotation (their own or received)
- Bot generates a formal Purchase Order PDF
- PO includes: PO number, date, vendor details, items, delivery terms, payment terms
- PO number auto-incremented from `company_profiles.invoice_counter`
- Create `processors/po_generator.py`

#### E-way Bill Generator
- Required for goods shipments > ₹50,000 value
- User uploads invoice → Bot extracts data → Generates e-way bill JSON
- Future: direct integration with NIC portal API (https://ewaybillgst.gov.in/apidocs)
- For MVP: generate the filled form as PDF for manual submission
- High pain point — people will pay specifically for this feature

#### Payment Reminder + Follow-up
- After a quotation is generated, bot asks: "Want to set a follow-up reminder?"
- User picks: 3 days / 7 days / 14 days
- Store reminder in DB with `remind_at` timestamp
- Background job (Celery beat) checks DB every hour and sends reminder message
- Reminder template: auto-generated professional follow-up message
- Requires Celery + Redis task queue (add in Month 2 anyway)

---

### 🔲 Month 4 — Scale & Polish

#### Celery Worker (Background Processing)
- Move all document processing out of the bot into Celery tasks
- Bot submits job → Celery processes → Bot polls for result
- Enables processing for web dashboard uploads without blocking
- Create `services/worker/` directory
- Add `worker` and `flower` (monitoring) to docker-compose

#### Analytics Dashboard
- PostHog integration (self-hosted or cloud)
- Track: feature usage, drop-off points, plan conversions
- Add PostHog JS snippet to web dashboard
- Add PostHog Python SDK to API for server-side events

#### Team Accounts
- Multiple users per organization
- Roles: `owner`, `admin`, `member`
- Invite by email
- Usage quota shared across the team
- `POST /api/v1/orgs/{org_id}/invite` endpoint

#### API Access for Developers
- Issue API keys per organization
- Allow programmatic document processing via REST API
- Rate limiting per plan
- API documentation (already exists at `/docs` in dev mode)

---

## 11. Go-to-Market Strategy

### Target Market (India First)
- **Primary**: Small manufacturing, trading, and services companies (1–50 employees)
- **Verticals**: Scientific instruments, industrial equipment, construction materials, chemicals, electrical goods
- **Geography**: Tier 2 and Tier 3 cities (Roorkee, Meerut, Ludhiana, Surat, Rajkot)
- **Why them**: High quotation volume, poor existing tooling, willing to pay for time savings

### Acquisition Channels
1. **Telegram groups** — Industry-specific groups (scientific equipment dealers, industrial suppliers). Drop the bot link.
2. **WhatsApp status** — Post "before/after" comparisons of quotation quality
3. **LinkedIn** — Target procurement managers at SMEs
4. **Google Ads** — Target "quotation format", "bill format India", "invoice maker India"
5. **CA/GST consultant referrals** — Partner with accountants who recommend tools to clients

### Pricing (Planned)
| Plan | Price | Docs/month | Target user |
|------|-------|-----------|-------------|
| Free | ₹0 | 10 | Try before buy |
| Starter | ₹499/mo | 100 | Freelancer / sole proprietor |
| Pro | ₹1,499/mo | 500 | Small business (5-15 staff) |
| Business | ₹3,999/mo | Unlimited | Medium business (15-50 staff) |

### USPs (Unique Selling Points)
1. **GST-native** — Built for India's tax structure (HSN codes, IGST/CGST/SGST, e-way bills)
2. **No formatting work** — Upload any competitor's quote, get it in your format in seconds
3. **Works on Telegram** — No app to install, no learning curve
4. **Your branding** — Documents come out with your company name, logo, GSTIN
5. **Audit trail** — Every document logged with timestamp

---

## 12. Features That Are India-Specific vs. Global

### India-Only Features (keep as India product)
- GST Invoice Validator (HSN codes, IGST/CGST/SGST structure)
- E-way Bill Generator (NIC portal specific)
- Bill to Make (Indian invoice format with GST split)
- Number to words in Indian system (Lakh, Crore)
- Razorpay payment gateway

### Global-Ready Features (can expand internationally)
- Sister Quotation (any quotation format, any currency)
- PDF/Excel/DOCX conversions
- Image watermarking
- Background removal
- Product catalog PDF
- Quotation comparison
- File rename

### If Going Global
- Remove India-specific features from global tier
- Add currency selector in company profile (currently hardcoded ₹)
- Add Stripe as payment gateway (alongside Razorpay for India)
- Add language/locale support for document templates
- Rename "GST" to "VAT/Tax" in UI

---

## 13. Competitor Analysis

| Tool | What they do | Gap DocSeva fills |
|------|-------------|-------------------|
| Vyapar | GST billing software | No document conversion, no Telegram |
| Zoho Invoice | Professional invoicing | Expensive, complex, no bot |
| ClearTax | GST filing | Tax-focused, no document tools |
| MS Word templates | DIY formatting | Time-consuming, error-prone |
| None | Sister quotation | This is unique — no competitor |

---

## 14. Key People / Context

- **Owner / Founder**: Akarshit Jain
- **Original company**: Sanmati Enterprises (scientific instruments, Roorkee)
- **Original bot**: `/Users/Akarshit.jain/Desktop/AI Project/quotation-agent/`
- **DocSeva project**: `/Users/Akarshit.jain/Desktop/DocSeva/`
- **Telegram bot token**: In `.env` file (not committed to git)
- **OpenAI key**: In `.env` file (not committed to git)

---

## 15. What to Work on Next (Immediate Tasks)

When picking up this project, the immediate priorities are:

1. **Fix the `version` deprecation warning** in `docker-compose.yml` — remove `version: "3.9"` line
2. **Move session store to Redis** — replace dict in `session_store.py` with Redis-backed JSON store
3. **Add `.dockerignore`** to bot service to speed up Docker builds
4. **Add retry logic** to `api_client.py` using `tenacity` library
5. **Start web dashboard** — create `services/dashboard/` with Next.js 14 app
6. **Add JWT auth** to API for web dashboard users
7. **Integrate Razorpay** for subscription payments
8. **Set up WhatsApp** via WATI integration

---

*Last updated: May 31, 2026*
*Written by: AI agent during DocSeva MVP development session*
