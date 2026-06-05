#genai: DocSeva API — FastAPI application entry point.
from __future__ import annotations

import asyncio
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.storage import ensure_buckets
from app.routes import (
    auth,
    auth_web,
    channels,
    documents,
    dpdp,
    health,
    me,
    process,
    profile,
    sister_formats,
)

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="DocSeva API",
    description="Multi-tenant document automation platform for Indian MSMEs.",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
#genai: Sprint 1 / WS-A — Web (JWT) auth + channel-link routes.
app.include_router(auth_web.router)
app.include_router(channels.router)
app.include_router(profile.router)
app.include_router(documents.router)
app.include_router(sister_formats.router)
#genai: Sprint 1 / WS-C scaffolding (Sprint 2 implementation) — generic /process/<feature>.
app.include_router(process.router)
#genai: Sprint 3 / WS-F — JWT-keyed /me/* routes for the web app.
app.include_router(me.router)
#genai: Sprint 6 — DPDP compliance: export + account deletion.
app.include_router(dpdp.router)


async def _warmup_rembg() -> None:
    """
    Pre-load the U-2-Net background-removal model in the background so the very
    first /process/bg_remove request doesn't pay the ~30 s download cost.

    Runs as a fire-and-forget task — the API serves other endpoints immediately
    while this completes. If rembg isn't installed the warmup is silently
    skipped so the API still starts cleanly.

    Combined with the persistent `rembg_models` volume in docker-compose, this
    download only happens on the very first start on a fresh host; subsequent
    restarts find the model already on disk and finish in ~1 s.
    """
    try:
        from rembg import new_session  # type: ignore
    except ImportError:
        logger.info("rembg not installed — bg-remove warmup skipped")
        return
    try:
        await asyncio.to_thread(new_session, "u2net")
        logger.info("rembg U-2-Net session ready")
    except Exception as exc:  # network blip, disk full, etc.
        logger.warning("rembg warmup failed (will retry on first request): %s", exc)


# Module-level reference so the warmup task isn't garbage-collected before it
# finishes — Python tasks must be held somewhere for the GC to leave them alone.
_BACKGROUND_TASKS: set[asyncio.Task[None]] = set()


@app.on_event("startup")
async def startup() -> None:
    logger.info("DocSeva API starting up (env=%s)", settings.environment)
    try:
        ensure_buckets()
        logger.info("MinIO buckets ready")
    except Exception as exc:
        logger.warning("MinIO not ready yet: %s", exc)
    # rembg warmup disabled on production to prevent OOM on small droplets.
    # The model loads on first actual bg_remove request (~5s with cached volume).
    # Re-enable by setting REMBG_WARMUP=true in .env on a 4GB+ server.
    if os.environ.get("REMBG_WARMUP", "").lower() == "true":
        task = asyncio.create_task(_warmup_rembg())
        _BACKGROUND_TASKS.add(task)
        task.add_done_callback(_BACKGROUND_TASKS.discard)
    else:
        logger.info("rembg warmup skipped (set REMBG_WARMUP=true to enable)")


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("DocSeva API shutting down")
