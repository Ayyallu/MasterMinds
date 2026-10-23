import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.db import engine

logger = logging.getLogger("masterminds")

settings = get_settings()

app = FastAPI(title="MasterMinds API", version="0.1.0")

# Explicit origin only. allow_credentials with a wildcard origin is invalid and
# must never be configured.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _check_database() -> bool:
    """Run a bounded `SELECT 1` readiness probe against the database."""
    async def _probe() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_probe(), timeout=settings.health_db_timeout_seconds)
        return True
    except (asyncio.TimeoutError, Exception):  # noqa: BLE001
        # Log server-side; never leak driver/internal details to the client.
        logger.warning("Database readiness probe failed", exc_info=True)
        return False


@app.get("/health")
async def health() -> JSONResponse:
    db_ok = await _check_database()
    status = "ok" if db_ok else "unavailable"
    code = 200 if db_ok else 503
    return JSONResponse(
        status_code=code,
        content={"status": status, "database": "up" if db_ok else "down"},
    )
