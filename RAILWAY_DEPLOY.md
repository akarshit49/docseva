# Railway Deployment Guide — Step by Step

> Plain-language guide. No technical experience assumed.
> Estimated time: 45–60 minutes the first time.

---

## Before you start — generate two secrets

Open Terminal on your Mac and run this **twice** to generate two unique secret strings:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```



Save both outputs — you'll use them as:
- **SECRET_1** → `API_SECRET_KEY` (used by API + Web).  beaf0f2452aed30dc95c6939c157c43d829cf06a21d62a404fd9d9f82751e620
- **SECRET_2** → `MINIO_SECRET_KEY` / `MINIO_ROOT_PASSWORD` (used by MinIO + all services that access files).   1c395360b01fe28fad5c4cf2e9d24bd6e3b004073fb0a7f7cf31e65b00d5d284

Also generate one more for the bot token:
```bash
python3 -c "import secrets; print(secrets.token_hex(16))"
```
- **SECRET_3** → `API_BOT_TOKEN` / `WA_API_BOT_TOKEN`
5bb14dcfd19f8c13d3725febfe30d270
---
MINIO_PUBLIC_ENDPOINT : minio-production-ac3d.up.railway.app

## STEP 1 — Create Railway account

1. Go to **[railway.app](https://railway.app)**
2. Click **"Login"** → **"Login with GitHub"**
3. Authorise Railway to access your GitHub
4. You're in. Railway gives you **$5 free credit** (enough for ~3 days of testing)

> To go beyond the free credit, click your name top-right → **Billing** → add a card.
> Cost estimate: ~$15–25/month for all 8 services running together.

---

## STEP 2 — Create a new Railway project

1. Click **"New Project"**
2. Choose **"Empty Project"**
3. Name it `docseva` (click the project name at the top to rename)

You now have a blank canvas. You'll add services one by one in the following steps.

---

## STEP 3 — Add PostgreSQL (database)

1. Inside your project, click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway creates and starts a Postgres database automatically
3. Click the Postgres service → **"Variables"** tab → you'll see `DATABASE_URL`, `PGHOST`, `PGUSER`, etc. — Railway fills these automatically. **You don't need to do anything here.**

---

## STEP 4 — Add Redis (cache / OTP storage)

1. Click **"+ New"** → **"Database"** → **"Add Redis"**
2. Railway creates Redis automatically
3. Same as Postgres — variables are filled automatically. Nothing to do.

---

## STEP 5 — Add MinIO (file storage)

MinIO stores all your uploaded documents and generated PDFs.

1. Click **"+ New"** → **"Docker Image"**
2. Image name: `minio/minio`
3. Click **"Add Service"**
4. Click the MinIO service → **"Settings"** tab:
   - Change service name to: `minio`
   - Scroll to **"Custom Start Command"** → paste the FULL command including `minio`:
     ```
     minio server /data --console-address ":9001"
     ```
   > ⚠️ Do NOT omit the word `minio` at the start — Railway will fail with
   > "executable 'server' could not be found" if you do.
5. Still in **"Settings"** → scroll to **"Networking"** section:
   - Under **"Private Networking"**: set port to `9000`
   - Under **"Public Networking"**: click **"Generate Domain"** — copy the URL.
     It looks like: `minio-production-xxxx.up.railway.app`
     **Save this URL** — you'll need it as `MINIO_PUBLIC_ENDPOINT` in later steps.
6. Click the MinIO service → **"Variables"** tab → add these (replace values):
   ```
   MINIO_ROOT_USER=minioadmin
   MINIO_ROOT_PASSWORD=SECRET_2_from_above
   ```
7. Click **"Volumes"** tab → **"Add Volume"**:
   - Mount path: `/data`
   - This makes your files survive Railway restarts.

---

## STEP 6 — Add the API service

This is the Python backend — the brain of the whole product.

1. Click **"+ New"** → **"GitHub Repo"** → select your `docseva` repo
2. Railway asks for settings:
   - **Root Directory**: `services/api`
   - **Dockerfile Path**: `Dockerfile`
3. Click **"Deploy"** (it will fail for now — we need to add env vars first)
4. Change service name to `api` (click Settings → rename)
5. Click **"Variables"** tab → click **"Raw Editor"** → paste the contents of the
   **"API service variables"** section from `.env.railway`, then fill in your real values:
   - Replace `CHANGE_ME_long_random_string` with **SECRET_1**
   - Replace `CHANGE_ME_strong_minio_password_here` with **SECRET_2**
   - Replace `CHANGE_ME_internal_bot_token` with **SECRET_3**
   - Replace `minio-production-XXXX.up.railway.app` with the MinIO URL from Step 5
   - Replace `sk-your_openai_key_here` with your real OpenAI key
   - Replace Resend key with your real Resend key (from [resend.com](https://resend.com))
6. For Postgres variables, use Railway's **"Add Reference"** button:
   - `POSTGRES_HOST` → Reference → Postgres → `PGHOST`
   - `POSTGRES_PORT` → Reference → Postgres → `PGPORT`
   - `POSTGRES_DB` → Reference → Postgres → `PGDATABASE`
   - `POSTGRES_USER` → Reference → Postgres → `PGUSER`
   - `POSTGRES_PASSWORD` → Reference → Postgres → `PGPASSWORD`
7. For `REDIS_URL`: Add Reference → Redis → `REDIS_URL`
8. Click **"Deploy"** — watch the build logs. Should go green in 3–5 minutes.
9. Click **"Networking"** → **"Generate Domain"** → copy your API URL.
   Looks like: `api-production-xxxx.up.railway.app`

---

## STEP 7 — Add the Web service

This is the Next.js website your users visit.

1. Click **"+ New"** → **"GitHub Repo"** → same `docseva` repo
2. Settings:
   - **Root Directory**: `services/web`
   - **Dockerfile Path**: `Dockerfile`
3. Change service name to `web`
4. **Variables** → Raw Editor → paste the **"Web service variables"** from `.env.railway`:
   - Replace `CHANGE_ME_long_random_string` with **SECRET_1** (same as API)
   - `API_INTERNAL_URL` stays as `http://api.railway.internal:8000` (Railway private network)
5. Click **"Deploy"** → wait 3–5 minutes for Next.js to build
6. Click **"Networking"** → **"Generate Domain"** → this is your **website URL** 🎉
   Share this URL with users: `web-production-xxxx.up.railway.app`

---

## STEP 8 — Add the Telegram Bot

1. Click **"+ New"** → **"GitHub Repo"** → same `docseva` repo
2. Settings:
   - **Root Directory**: *(leave blank — the bot needs the whole project root)*
   - **Dockerfile Path**: `services/bot/Dockerfile`
3. Change service name to `bot`
4. **Variables** → Raw Editor → paste the **"Bot (Telegram) service variables"** from `.env.railway`:
   - Fill in your real Telegram bot token
   - Replace all `CHANGE_ME` and `XXXX` values
5. Click **"Deploy"**

---

## STEP 9 — Add the WhatsApp Bot *(optional — skip if not using WhatsApp yet)*

1. Click **"+ New"** → **"GitHub Repo"** → same `docseva` repo
2. Settings:
   - **Root Directory**: `services/bot-whatsapp`
   - **Dockerfile Path**: `Dockerfile`
3. Change service name to `bot-whatsapp`
4. **Variables** → Raw Editor → paste the **"Bot-WhatsApp service variables"** from `.env.railway`
5. Click **"Deploy"**

---

## STEP 10 — Verify everything is working

1. Open your **web URL** (from Step 7) in a browser
2. You should see the DocSeva login page
3. Enter your email → request OTP → check your email inbox for OTP
4. Login → you're in → try creating a quotation
5. Open your **API URL** + `/health` (e.g., `api-production-xxxx.up.railway.app/health`) → should return `{"status":"ok"}`

---

## STEP 11 — Connect your custom domain *(optional)*

Once everything works on the Railway URLs:

1. Buy your domain (e.g., `glyph.io`) from Namecheap / GoDaddy
2. In Railway → web service → **Networking** → **"Custom Domain"** → type `www.yourdomain.com`
3. Railway shows you a **CNAME record** to add
4. Log into your domain registrar → DNS settings → add that CNAME record
5. Wait 10–30 minutes → your site is live on your own domain

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails with "no such file" | Check Root Directory is set correctly for that service |
| API health check fails | Check Variables — especially POSTGRES_* refs are set |
| Web shows "Internal Server Error" | Check `API_INTERNAL_URL` in web variables is `http://api.railway.internal:8000` |
| Files not uploading | Check MinIO variables and that the Volume is attached |
| OTP not arriving by email | Check `EMAIL_PROVIDER=resend` and `RESEND_API_KEY` is correct |
| Service keeps restarting | Click the service → "Logs" tab → read the error message |

---

## Cost breakdown (approximate)

| Service | Monthly cost |
|---|---|
| PostgreSQL (Railway managed) | ~$5 |
| Redis (Railway managed) | ~$3 |
| MinIO service + Volume (1GB) | ~$3 |
| API (512MB RAM) | ~$5 |
| Web (512MB RAM) | ~$3 |
| Bot (256MB RAM) | ~$2 |
| WhatsApp Bot (256MB RAM) | ~$2 |
| **Total** | **~$23/month** |

Railway's Hobby plan ($5 credit free) covers testing. For production add a credit card — you only pay for what you use.

---

## After deploying — keeping it updated

Every time you make code changes on your Mac:

```bash
cd /Users/Akarshit.jain/Desktop/DocSeva
git add .
git commit -m "describe what changed"
git push https://akarshit49:YOUR_TOKEN@github.com/akarshit49/docseva.git main
```

Railway automatically detects the push and re-deploys all services. Usually takes 3–5 minutes.
