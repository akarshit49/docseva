# DocSeva — Human Runbook (Pre-Launch + Day-1 Ops)

<!-- #genai: Sprint 6 wrap-up — operator's guide bridging "code done" → "20 dealers using it" -->

This file lists everything a human must do — across signup, vendor setup,
configuration, deployment, and real-world testing — to take DocSeva from
"code is written" to "20 dealers using it". Work top-to-bottom.

Estimated time end-to-end: **6–10 hours of human work**, spread across
2–3 calendar days (some items wait on Meta / WATI approvals).

---

## Phase 0 — Local Smoke (you can do this today, 30 min)

Validate the whole stack on your laptop before touching prod.

### 0.1 Prereqs
- Docker Desktop ≥ 4.30 with at least 4GB RAM allotted
- Python 3.12 + venv (only needed if you want to run pytest outside Docker)
- Node 20+ (only if you want to run the web app outside Docker)
- `k6` (`brew install k6`) — for smoke + load tests

### 0.2 Config
```bash
cd /Users/Akarshit.jain/Desktop/DocSeva
cp .env.example .env
```
Edit `.env` and set at minimum (everything else can stay default for local):
- `API_SECRET_KEY` → any long random string (`openssl rand -hex 32`)
- `API_BOT_TOKEN` → any long random string (the same string also goes into `WA_API_BOT_TOKEN`)
- `OPENAI_API_KEY` → your real OpenAI key (the parsers need it)
- `EMAIL_PROVIDER=log` (default — OTPs print to API logs, fine for local)
- `TELEGRAM_BOT_TOKEN` → leave blank for now if you don't have a TG bot
- `WA_BSP_PROVIDER=mock` (default — uses in-memory mock BSP)

### 0.3 Boot
```bash
docker-compose up --build -d
docker-compose ps            # all services should be "healthy" within ~60s
docker-compose logs -f api   # watch migrations finish
```

### 0.4 Click around
| URL                                    | What to do                                          |
| -------------------------------------- | --------------------------------------------------- |
| `http://localhost`                     | Landing page → click "Get started"                  |
| `http://localhost/login`               | Enter your email, click "Send code"                 |
| Get OTP                                | `docker-compose logs api \| grep OTP`               |
| Enter OTP                              | You land on `/dashboard`                            |
| Complete setup wizard                  | Add display name + GSTIN, upload a logo             |
| Upload a tender format                 | `/library/formats` → drop your DOCX template        |
| Run the anchor flow                    | `/new-quote` → drop a supplier PDF                  |

### 0.5 Verify each test layer

```bash
# Backend tests
cd services/api          && ../../.venv/bin/python -m pytest tests/ -q
cd services/bot-whatsapp && ../../.venv/bin/python -m pytest tests/ -q
cd services/bot          && TELEGRAM_BOT_TOKEN=test OPENAI_API_KEY=test \
    ../../.venv/bin/python -m pytest tests/ -q

# Web unit tests (Vitest)
cd services/web          && npm test

# Web E2E tests (Playwright, optional — needs services up first)
cd services/web          && npm run test:e2e

# Smoke test
k6 run loadtests/smoke.js
```
All should be green.

### 0.6 Test WhatsApp adapter locally (using the mock BSP)

The mock BSP accepts a simple JSON shape so you can simulate a WhatsApp
user without a WATI account:

```bash
# First message — bot will ask for the business name
curl -X POST http://localhost:8080/whatsapp/webhook \
  -H "Content-Type: application/json" \
  -d '{"from":"+919900000001","kind":"text","text":"hi","message_id":"m1"}'

# Reply with the business name
curl -X POST http://localhost:8080/whatsapp/webhook \
  -H "Content-Type: application/json" \
  -d '{"from":"+919900000001","kind":"text","text":"Acme Instruments","message_id":"m2"}'

# Check what the bot would have sent (mock outbox lives in process memory;
# in tests we assert against it, in dev you'd see it in the logs)
docker-compose logs bot-whatsapp | tail -50
```

---

## Phase 1 — Vendor Accounts (≈2 hours, mostly waiting)

### 1.1 Domain + SSL
- [ ] Buy `docseva.in` (or your chosen domain) on a registrar (GoDaddy, Cloudflare Registrar).
- [ ] Point `A` records for `docseva.in`, `api.docseva.in`, `files.docseva.in` to your server IP.
- [ ] Issue Let's Encrypt certs (`certbot --nginx`) — run on the host where nginx lives.

### 1.2 Telegram bot
- [ ] Open Telegram, message `@BotFather`.
- [ ] `/newbot` → name "DocSeva" → username `docseva_bot` (or whatever's free).
- [ ] Copy the token, paste into `.env` as `TELEGRAM_BOT_TOKEN`.
- [ ] `/setdescription` and `/setabouttext` for a polished profile.
- [ ] (Optional but recommended) `/setcommands` to add `/start /help /history /settings`.

### 1.3 WhatsApp Business via WATI
- [ ] Sign up at https://www.wati.io → "Get a number" → use a fresh business SIM (any number you DON'T use personally).
- [ ] Complete the Meta Business verification (this is the long one — can take 1–3 days; submit on Day 1).
- [ ] In WATI dashboard → API Settings → generate an API token. Paste into `.env` as `WA_WATI_API_TOKEN`.
- [ ] In WATI dashboard → Webhook → URL = `https://docseva.in/whatsapp/webhook`. Set the verify token = anything random, paste the same into `.env` as `WA_WATI_VERIFY_TOKEN`.
- [ ] Flip `.env`: `WA_BSP_PROVIDER=wati`.
- [ ] Submit message templates for approval (Meta-mandated for outbound business-initiated messages). Three to start:
  - `docseva_welcome`: "Welcome to DocSeva. Drop your supplier quote and I'll turn it into your branded quote in seconds."
  - `docseva_doc_ready`: "Your {{1}} is ready. {{2}}/{{3}} docs used this cycle."
  - `docseva_link_request`: "Use this code to link your WhatsApp to docseva.in: {{1}}. Code expires in 10 minutes."
  - Approvals take 24–48 hours.

### 1.4 OpenAI
- [ ] Generate a production key at platform.openai.com (separate from your dev key for usage tracking).
- [ ] Set a monthly hard limit (start with $100 — we use ~$0.02 per quote).
- [ ] Paste into `.env` as `OPENAI_API_KEY`.

### 1.5 Email delivery (Resend recommended)
- [ ] Sign up at resend.com (free for 3k emails/month).
- [ ] Verify your domain (DKIM + SPF records — registrar UI).
- [ ] Generate API key → paste into `.env` as `RESEND_API_KEY`.
- [ ] Flip `.env`: `EMAIL_PROVIDER=resend`.

### 1.6 Object storage (production MinIO or AWS S3)
For launch you can keep MinIO; here's the production checklist either way:
- [ ] If self-hosted MinIO: deploy on a separate volume with at least 100GB.
      Set strong `MINIO_ROOT_PASSWORD`. Open only port 9000 to the API container,
      9001 only to your IP for the console.
- [ ] If AWS S3: create three buckets `docseva-uploads`, `docseva-outputs`,
      `docseva-assets`. Set lifecycle policy to expire `outputs` after 30 days.
- [ ] Public endpoint goes into `MINIO_PUBLIC_ENDPOINT` (e.g. `files.docseva.in`).

### 1.7 Production database
- [ ] AWS RDS Postgres 16 (smallest = `db.t4g.small`, ~$25/mo) or managed
      Postgres on Render/Railway. Single instance is fine for v1 — backup
      enabled, retention 7 days.
- [ ] Plug the connection details into `.env`.

---

## Phase 2 — Deploy to Production (≈2 hours)

### 2.1 Server provisioning
- [ ] Single VPS with 4 CPU + 8GB RAM is enough for v1 (Hetzner CCX13 or
      AWS t4g.large work well — ~$35/mo).
- [ ] Install Docker + docker-compose + nginx + certbot.
- [ ] Clone the repo, copy `.env`, run `docker-compose up -d --build`.

### 2.2 Domain wiring
- [ ] Replace `nginx/nginx.conf` with HTTPS server block (cert paths to
      Let's Encrypt). The existing config goes inside the `server { ... }` block.
- [ ] Enable the rate-limit block documented in `SECURITY_REVIEW.md` §4.

### 2.3 Pre-launch sign-off — run through `SECURITY_REVIEW.md` §9
That checklist is the gate. Don't go live with any unchecked box.

### 2.4 Telegram webhook
```bash
curl -X POST "https://api.telegram.org/bot$TG_TOKEN/setWebhook" \
     -d "url=https://api.docseva.in/telegram/webhook&secret_token=YOUR_SECRET"
```

### 2.5 Smoke + load
```bash
K6_BASE_URL=https://docseva.in k6 run loadtests/smoke.js
K6_API_URL=https://api.docseva.in K6_BOT_TOKEN=$API_BOT_TOKEN \
  k6 run loadtests/sister_quote.js    # run against STAGING, never prod
```

---

## Phase 3 — Real-World Manual Test (≈2 hours, before any dealer sees it)

Do this on production *with your own accounts*. Mark each as ✅ when verified.

### 3.1 Web

- [ ] Open `https://docseva.in` on a phone (not just desktop) — landing page renders, CTA visible.
- [ ] Click "Get started" → enter your real email → receive OTP within 30s → enter it → land on `/dashboard`.
- [ ] Setup wizard appears. Fill profile → upload a real logo → upload a real tender DOCX → wizard says "Done".
- [ ] Anchor flow:
  - [ ] `/new-quote` → drop a real supplier PDF (the kind a dealer would get).
  - [ ] Step 2 shows parsed items in an editable table. Edit one row.
  - [ ] Step 3 → pick your saved format.
  - [ ] Step 4 → DOCX downloads. Open it — does it look right? Logo, GST, items, totals?
- [ ] `/settings/channels` → click "Connect Telegram" → deep link to your bot → click "Start" → reply with the code → web shows "linked".
- [ ] `/settings/channels` → "Connect WhatsApp" → copy code → send `/link <code>` to your business WA number → web shows "linked".
- [ ] `/settings/account` → "Download JSON" → file downloads and contains your data.
- [ ] `/settings/account` → "Delete my account" → confirms → cancels (or test deletion in a throwaway account).

### 3.2 Telegram

- [ ] Open Telegram → message your bot `/start` → it asks for business name → reply → it confirms.
- [ ] Send the same supplier PDF you used on the web. Same item count parses?
- [ ] Tap "Sister Quote" → confirm → pick format → receive a DOCX in chat.
- [ ] **Parity check**: download the DOCX. Diff it against the web's DOCX from §3.1 (same input + same format) — the items, totals, branding should be identical.

### 3.3 WhatsApp

- [ ] Save your business WA number, open WhatsApp → message it `hi`.
- [ ] Bot replies asking for business name → reply → confirms.
- [ ] Send the same supplier PDF. Same items parsed.
- [ ] Tap "Sister Quote" button → "✅ Looks good" → pick format from list → DOCX arrives.
- [ ] **Parity check**: same as 3.2 — the WA-generated DOCX should match web + TG byte-for-byte for the same input + format.
- [ ] Send `/help`, `/cancel`, `/link <bad_code>` — make sure error paths are clean.

### 3.4 Cross-cutting

- [ ] Free plan quota: generate 10 docs across any channel. The 11th must show the "upgrade" message *on every channel*.
- [ ] DPDP delete: in a throwaway account, hit delete → log out → log back in → check that you cannot. The account is frozen.
- [ ] Logs: `docker-compose logs api | grep ERROR` should be empty. Any error during your tests is a bug to fix before launch.

---

## Phase 4 — Soft Launch (Week 1)

### 4.1 Pick the cohort
20 dealers from the Sanmati network (the audience the plan already
validated). Don't over-recruit — small enough to give each a 15-min
onboarding call.

### 4.2 Communicate
- [ ] WhatsApp blast (template-approved) explaining what DocSeva does and
      the docseva.in URL.
- [ ] Personal 15-min call with each dealer:
      - Send them a real supplier PDF over WhatsApp.
      - Watch them complete the anchor flow.
      - Note where they hesitate — that's your highest-leverage UX fix.

### 4.3 Metrics to watch daily
| Metric                                   | Source                                    | Target            |
| ---------------------------------------- | ----------------------------------------- | ----------------- |
| Anchor flow conversion (drop → DOCX)     | API logs grouped by user                  | > 80%             |
| p(95) of `/process/sister_quote` final   | nginx logs / k6                           | < 8s              |
| Error rate                               | `docker-compose logs api \| grep ERROR`   | < 1% of requests  |
| Quote→bill ratio (Phase 2 hint)          | `documents` table                         | tracked, no target yet |
| Channel mix (web vs TG vs WA)            | `usage_events.channel`                    | informs Phase 2 priority |

### 4.4 Iterate
End-of-week: review the call notes + metrics. Pick the **single biggest
friction point** and fix it for week 2. Don't pile up TODOs — close one
sharp loop at a time.

---

## Appendix A — What to do if something goes wrong

| Symptom                              | First check                                                                  |
| ------------------------------------ | ---------------------------------------------------------------------------- |
| Web shows "Couldn't reach API"       | `docker-compose ps`, then `docker-compose logs nginx api`                    |
| OTP never arrives                    | `EMAIL_PROVIDER` value; resend dashboard for delivery status                 |
| Telegram bot offline                 | Webhook URL set correctly? `curl https://api.telegram.org/bot$TOKEN/getWebhookInfo` |
| WhatsApp messages not delivering     | WATI dashboard → Messages tab. Template name approved? Verify token matches? |
| OpenAI errors                        | Check usage limits at platform.openai.com. Switch to fallback `gpt-4o-mini`. |
| MinIO presigned URL 404              | `MINIO_PUBLIC_ENDPOINT` reachable from user's network (not docker internal)? |
| "Quota exceeded" appearing wrongly   | `SELECT docs_used_this_cycle FROM organizations WHERE id = ?` — reset if mis-counted |

## Appendix B — Things explicitly NOT done yet (Phase 2 backlog)

These are called out in `SECURITY_REVIEW.md` and the execution plan as
post-launch work:

- ClamAV virus scanning on uploads
- Hard-delete cron job (today: 30-day soft delete only)
- Multi-user / team accounts (today: 1 owner per org)
- More Playwright E2E coverage (today: 2 specs ship; add the rest pre-launch)
- Dependabot / automated SCA
- Secrets in a vault (today: `.env` on disk)
- AWS Secrets Manager / multi-region

If a dealer asks "when can my team access this together?", that's the
Phase-2 trigger — don't build it preemptively.

---

## Appendix C — Quick reference for test coverage

After Sprint 6, the test surface looks like:

| Surface              | Tool       | Tests | Coverage |
| -------------------- | ---------- | ----: | -------: |
| API                  | pytest     |    62 |     ~27% statements / **~90% on processors** (covered via bot suite) |
| Telegram bot         | pytest     |   325 |     ~68% |
| WhatsApp adapter     | pytest     |    18 |     ~63% |
| Web (unit)           | Vitest     |   ~14 |     n/a (component-level smoke + lib coverage) |
| Web (E2E)            | Playwright |     2 |     anchor flow + login |
| Load                 | k6         |     2 |     smoke + sister_quote |

Run everything with the commands in §0.5.
