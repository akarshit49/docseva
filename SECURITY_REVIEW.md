# Security Review — Pre-Launch (Sprint 6)

Last reviewed: 2026-06-01.
Scope: everything shipped in Sprints 1–6 of `EXECUTION_PLAN_MULTI_CHANNEL.md`.
Reviewer: parent owner (initial), external pen-test recommended pre-public-launch.

This document is a living checklist. Every item is either ✅ (verified in code),
🟡 (mitigated but improvable), or 🔴 (todo before public launch).

---

## 1. Authentication

| Risk | Status | Notes |
|---|---|---|
| Web auth uses email OTP + JWT refresh tokens | ✅ | `services/api/app/routes/auth_web.py`. OTPs expire in 10m, tokens rotate. |
| Refresh tokens stored as hashes, not plaintext | ✅ | `WebSession.refresh_token_hash` is SHA-256 of the raw token. |
| Bot adapters share a single `API_BOT_TOKEN` secret | ✅ | Rotate quarterly via env. Document the rotation runbook below. |
| WhatsApp BSP webhook authentication | ✅ | `WatiBsp.verify_signature` checks `WA_WATI_VERIFY_TOKEN` when set. **🔴 Must be set in prod**. |
| Telegram webhook secret token | 🟡 | TG webhooks rely on the secret URL path; layer a `secret_token` header check before public launch. |
| Channel-linking tokens are single-use, 10-minute TTL | ✅ | `_LINK_TTL_SECONDS = 600` in `channels.py`. |

### Bot token rotation runbook

1. Generate a new token: `openssl rand -hex 32`.
2. Update `.env` on the API + both bot services in parallel.
3. `docker-compose restart api bot bot-whatsapp` — accept a 2–5s downtime.
4. Revoke the old token by recycling the env (no on-disk allowlist exists).

---

## 2. File upload safety

| Risk | Status | Notes |
|---|---|---|
| Hard cap on upload size | ✅ | Nginx `client_max_body_size 20M`; FastAPI rejects > 15MB. |
| Mime-type whitelist | ✅ | `services/api/app/processors/service.py` validates extensions before any processing. |
| WhatsApp adapter rejects non-document attachments | ✅ | `ACCEPTED_SUFFIXES` in `services/bot-whatsapp/app/conversation.py`. |
| Path traversal via uploaded filenames | ✅ | All uploads are written to MinIO with server-generated keys (`uploads/{uuid}/...`). User-controlled filenames are never used as paths. |
| Stored documents are quarantined per organization | ✅ | MinIO bucket policy is `org_id` prefixed; cross-org reads are rejected by the API even if a key leaks. |
| Virus scanning | 🔴 | Add ClamAV sidecar before processing PDFs from untrusted senders. Track as Phase 2. |

---

## 3. Presigned URLs

| Risk | Status | Notes |
|---|---|---|
| Presigned URLs are short-lived | ✅ | `PRESIGNED_URL_EXPIRY=86400` (24h) by default. Reduce to 1h once the web UI implements one-click "regenerate link". |
| Presigned URLs are scoped to a single object | ✅ | MinIO presign is per-key. |
| Presigned URLs are channel-attributable | ✅ | The API logs `caller.channel` + `caller.user_id` on every presign call (`structured_logging.json_log`). |
| Public URL host is configurable | ✅ | `MINIO_PUBLIC_ENDPOINT` separate from internal docker address. |
| URLs leak via referer / browser history | 🟡 | Mitigated by short TTL. Pre-launch: set `Referrer-Policy: no-referrer` for the web download links. |

---

## 4. Rate limiting

We layer this in nginx + the API:

| Layer | Limit | Notes |
|---|---|---|
| Nginx — `/api/auth/*` | 10 req/min/IP | Stops OTP brute force at the edge. **🟡 not yet enabled** — config block below. |
| Nginx — `/whatsapp/webhook` | 60 req/sec | Generous; BSPs batch. |
| API — `/process/<feature>` | Per-quota (free=10/mo etc.) | Already enforced by `OrganizationDocs` quota in `auth.py`. |
| API — `/auth/request-otp` | 5 req/15min/email | **🟡 todo** — add a SQL window check. |

### Nginx rate-limit block (add before launch)

Append to `nginx/nginx.conf`:

```nginx
http {
  limit_req_zone $binary_remote_addr zone=docseva_auth:10m rate=10r/m;
  limit_req_zone $binary_remote_addr zone=docseva_api:10m  rate=60r/s;

  server {
    location /api/auth/ {
      limit_req zone=docseva_auth burst=20 nodelay;
      # ... existing proxy_pass ...
    }
    location /api/v1/ {
      limit_req zone=docseva_api burst=120 nodelay;
      # ... existing proxy_pass ...
    }
  }
}
```

---

## 5. PII & DPDP compliance

| Requirement | Status | Notes |
|---|---|---|
| Right to access | ✅ | `GET /api/v1/me/account/export` returns a JSON dump (Sprint 6). |
| Right to erasure | ✅ | `POST /api/v1/me/account/delete` schedules deletion with 30d grace. |
| Hard purge job runs after grace period | 🔴 | Cron job not yet implemented — track as a Phase-2 follow-up. |
| Logs scrub PII | 🟡 | `structured_logging` strips JWT bodies; phone numbers + emails still appear in error logs. Add a redaction filter before launch. |
| Data residency | ✅ | Postgres + MinIO are deployed in `ap-south-1`; no cross-border data movement. |
| User can re-issue forgotten passwords | n/a | Web auth is OTP — no passwords to forget. |

---

## 6. Channel-specific risks

### Telegram
- ✅ `getUpdates`-based polling is rate-limited by Telegram itself.
- 🟡 We don't yet validate the webhook signature. Switch to webhook mode + `secret_token` header before public launch.

### WhatsApp
- ✅ BSP verify token enforced when `WA_WATI_VERIFY_TOKEN` is set.
- ✅ Webhook dedupes by `message_id` so accidental BSP replays are no-ops.
- 🟡 We log raw inbound payloads at DEBUG. Disable in production (`WA_LOG_LEVEL=INFO`).
- 🔴 Approved template content not yet submitted to Meta — block list of allowed templates in code once provisioning is complete.

### Web
- ✅ JWT cookies are `httpOnly` + `Secure` + `SameSite=Lax`.
- ✅ Refresh path is server-side only (route handler in `app/api/auth/refresh`).
- 🟡 No CSP headers yet. Add a strict default-src self before launch.

---

## 7. Secrets management

- ✅ All secrets live in `.env`; nothing is committed (`.env.example` carries placeholders only).
- ✅ `docker-compose.yml` uses `env_file:` instead of inline env so secrets don't leak via `docker inspect`.
- 🟡 No vault/KMS yet — Phase 2: move to AWS Secrets Manager once we get serious about multi-region.

---

## 8. Dependency security

- ✅ Python deps pinned in `requirements.txt`; review monthly.
- ✅ Web deps locked via `package-lock.json`.
- 🟡 No automated SCA yet. Track: add a Dependabot config in Phase 2.

---

## 9. Pre-launch sign-off list (run through this before flipping DNS)

- [ ] `API_SECRET_KEY` and `API_BOT_TOKEN` rotated and not the `.env.example` defaults.
- [ ] `WA_WATI_VERIFY_TOKEN` configured on both sides (WATI console + our env).
- [ ] Nginx rate-limit block uncommented and reloaded.
- [ ] `MINIO_PUBLIC_ENDPOINT` points at the public HTTPS host, not LAN IP.
- [ ] CSP + Referrer-Policy headers added to nginx.
- [ ] Logs verified for no PII leakage (try a real document, grep for the email in `journalctl`).
- [ ] Smoke test green: `k6 run loadtests/smoke.js`.
- [ ] Load test green on staging: `k6 run loadtests/sister_quote.js`.
- [ ] DPDP export tested with a real account (download + open file).
- [ ] DPDP delete tested + grace-period UI verified.
- [ ] Cross-channel parity test green: `pytest services/api/tests/test_sprint6_parity.py`.
- [ ] Backup + restore drill completed for Postgres in the last 7 days.

---

*This document is what we hand to the external auditor pre-launch. Update it
every time we ship something that changes the threat model.*
