# DocSeva — Smart Document Automation for Indian MSMEs

Multi-tenant SaaS platform for document automation. Each company gets its own profile, branding, and quota. Currently delivered via Telegram bot.

## Architecture

```
Telegram ──► Bot Service (Python)
                │
                ▼ REST (X-Bot-Token)
             API Service (FastAPI)
                │
         ┌──────┼──────┐
         ▼      ▼      ▼
      Postgres Redis  MinIO
```

| Service | Port | Purpose |
|---------|------|---------|
| `api` | 8000 | REST API — auth, profile, document logging |
| `bot` | — | Telegram polling bot |
| `postgres` | 5432 | Primary database |
| `redis` | 6379 | Session cache, future task queue |
| `minio` | 9000/9001 | Object storage (uploads, outputs, logos) |

---

## Quick Start (Local)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Docker Compose)

### 1. Configure

```bash
cd /path/to/DocSeva
cp .env.example .env
```

Edit `.env` — at minimum, set:
- `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather)
- `OPENAI_API_KEY` — from [platform.openai.com](https://platform.openai.com)
- Change all `*_change_in_prod` passwords to strong random values

### 2. Build & Start

```bash
make build   # ~5-10 min first time (downloads models etc.)
make up      # start all services
```

Or without Make:
```bash
docker compose up --build -d
```

### 3. Verify

```
API docs   → http://localhost:8000/docs
MinIO UI   → http://localhost:9001  (login: values from .env)
Bot logs   → docker compose logs -f bot
```

### 4. Use

1. Find your bot on Telegram (the username you set in BotFather)
2. Send `/start`
3. Complete the 1-minute onboarding (your name → company name → phone → GSTIN)
4. Send any document or image!

---

## Features

### Document Processing
| Feature | Input | Output |
|---------|-------|--------|
| Sister Quotation | DOC/DOCX/PDF | DOCX (3 style choices) |
| Bill to Make | DOC/DOCX | PDF Invoice |
| PDF → DOCX | PDF | DOCX (layout preserved) |
| Excel → DOCX | XLS/XLSX | DOCX (table formatted) |
| Export to PDF | DOC/DOCX/Excel | PDF |
| Rename | Any | Same format, new name |
| GST Validator | Any invoice | Text report |
| Quotation Comparison | 2–5 quotations | DOCX comparison table |

### Image Processing
| Feature | Input | Output |
|---------|-------|--------|
| Add Watermark | PNG/JPG/HEIC | Same format |
| Remove Background | PNG/JPG/HEIC | PNG |
| Product Catalog PDF | Image + text | PDF |

### Multi-Tenancy
- Every Telegram user → own company profile
- Company logo, GSTIN, bank details stored in DB
- Monthly document quota per plan tier
- Document history

---

## Project Structure

```
DocSeva/
├── services/
│   ├── api/                   # FastAPI — auth, profile, document logging
│   │   ├── app/
│   │   │   ├── core/          # Config, DB, storage, security
│   │   │   ├── models/        # SQLAlchemy ORM models
│   │   │   ├── schemas/       # Pydantic request/response schemas
│   │   │   └── routes/        # API route handlers
│   │   └── alembic/           # Database migrations
│   │
│   └── bot/                   # Telegram bot
│       └── app/
│           ├── processors/    # All document/image converters
│           ├── handlers/      # Conversation handlers (onboarding, etc.)
│           ├── api_client.py  # HTTP client for API service
│           ├── bot.py         # Main bot logic
│           └── session_store.py  # In-memory state machine
│
├── assets/                    # Shared assets (logo.png)
├── nginx/                     # Nginx config for production
├── docker-compose.yml         # Local development
├── docker-compose.prod.yml    # Production overrides
└── Makefile                   # Convenience commands
```

---

## Environment Variables

See `.env.example` for the full list with descriptions.

Key variables:
| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From BotFather |
| `OPENAI_API_KEY` | For LLM-powered features |
| `POSTGRES_PASSWORD` | Change from default! |
| `MINIO_SECRET_KEY` | Change from default! |
| `API_SECRET_KEY` | Change from default! |
| `API_BOT_TOKEN` | Shared secret between bot and API |

---

## Quota / Plans

| Plan | Docs/month | Notes |
|------|-----------|-------|
| `free` | 10 | Default for new users |
| `starter` | 100 | — |
| `pro` | 500 | — |
| `business` | Unlimited | — |

Upgrade plans by directly updating the `organizations.plan` and `organizations.docs_limit_per_cycle` columns in the database (payment integration coming in Month 2).

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Register or resume session |
| `/menu` | Show quota and commands |
| `/settings` | Update company profile |
| `/history` | Last 10 processed files |
| `/help` | Feature overview |
| `/stop` | End current flow |

---

## Deployment (Production)

```bash
# On your server (Ubuntu 22.04 recommended)
git clone <your-repo> DocSeva
cd DocSeva
cp .env.example .env
# Edit .env with production values

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

For HTTPS, configure your domain in `nginx/nginx.conf` and add SSL certificates to `nginx/certs/`.

---

## Roadmap

- **Month 2**: WhatsApp integration (via WATI/Gupshup), Payment gateway (Razorpay), Web dashboard (Next.js)
- **Month 3**: Purchase Order generator, E-way bill generator, Payment reminder follow-up
- **Month 4**: Advanced analytics, team accounts, API access
