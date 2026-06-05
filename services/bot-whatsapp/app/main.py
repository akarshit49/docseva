#genai: Sprint 5 / WS-E — FastAPI entry point for the WhatsApp adapter.
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.config import get_settings
from app.webhook import router as webhook_router

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)

app = FastAPI(
    title="DocSeva — WhatsApp Adapter",
    description=(
        "Thin BSP-agnostic webhook → conversation → DocSeva API adapter. "
        "All processing lives in the API service."
    ),
    version="0.1.0",
)

app.include_router(webhook_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "bot-whatsapp"}
