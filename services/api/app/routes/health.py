#genai: Health check endpoint for Docker and load balancers.
from fastapi import APIRouter
from sqlalchemy import text

router = APIRouter()


@router.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "service": "docseva-api"}
