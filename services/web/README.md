# DocSeva Web

The Next.js web channel for DocSeva. Implements Sprints 3 & 4 of the
multi-channel execution plan: login (email OTP) → dashboard → anchor flow
(`/new-quote`) → library, tools, settings, billing.

## Run locally

```bash
cd services/web
cp .env.example .env.local      # set NEXT_PUBLIC_API_BASE_URL etc.
npm install
npm run dev                     # http://localhost:3000
```

The dev server proxies `/api/v1/*` to the FastAPI service (see
`next.config.js → rewrites`). When the API is running via `docker-compose`,
`API_INTERNAL_URL=http://api:8000` is already set in the compose file.

## Run with Docker Compose

```bash
docker-compose up --build web
```

The compose file routes `http://localhost/` to the web app and
`http://localhost/api/v1/*` to FastAPI via nginx.

## Architecture

- **App Router** (`app/`) with two route groups:
  - `(marketing)` — public landing/pricing/legal.
  - `(app)` — JWT-protected dashboard, anchor flow, tools, settings.
- **Auth** lives in `lib/auth.ts` + `app/api/auth/*` Next route handlers. The
  Next handlers proxy to FastAPI and set httpOnly cookies, so the access
  token never touches client JS.
- **API client** (`lib/api.ts`) is a typed wrapper around `fetch` that
  attaches the cookie's bearer token to every server-side call.
- **Forms** use `react-hook-form` + `zod`. Zod schemas in `lib/schemas.ts`
  mirror the Pydantic shapes on the API.
- **State** for the anchor flow lives in a single Zustand store
  (`lib/store/new-quote-store.ts`) so users can flip back/forward between
  steps without losing data.

## Anchor flow

`/new-quote` is the most important screen. Four steps:

1. Drop a supplier quote (PDF / DOC / DOCX).
2. Confirm extracted items (editable table — the "confirm before send" gate).
3. Pick output format (saved tender templates).
4. Done — download / share / make another / convert to invoice.

The wizard never re-uploads the file across steps; we keep a server-side
preview (via `/api/v1/process/sister_quote?mode=preview`) until the user
clicks "Generate" which switches to `mode=final`.
