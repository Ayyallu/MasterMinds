import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.routers import academic as academic_router
from app.routers import auth as auth_router
from app.routers import institutions as institutions_router
from app.routers import ai as ai_router
from app.routers import attempts as attempts_router
from app.routers import scoring as scoring_router
from app.routers import exams as exams_router
from app.routers import questions as questions_router

logger = logging.getLogger("masterminds")

settings = get_settings()

# Reject insecure development defaults when running in production.
settings.validate_production_secrets()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to warm; migrations run as a release step, not here.
    yield
    # Graceful shutdown: drain the connection pool.
    await engine.dispose()


app = FastAPI(title="MasterMinds API", version="0.1.0", lifespan=lifespan)

# Explicit origin only. allow_credentials with a wildcard origin is invalid and
# must never be configured. Config validation already rejects "*", but guard
# here too so the insecure combination can never reach the middleware.
_allow_credentials = True
_cors_origins = [settings.frontend_origin]
if _allow_credentials and "*" in _cors_origins:
    raise RuntimeError(
        "CORS misconfiguration: allow_credentials=True cannot be combined "
        "with a wildcard origin."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_allow_credentials,
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
    except asyncio.TimeoutError:
        logger.warning(
            "Database readiness probe timed out after %ss",
            settings.health_db_timeout_seconds,
        )
        return False
    except Exception:  # noqa: BLE001
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


app.include_router(auth_router.router)
app.include_router(institutions_router.router)
app.include_router(academic_router.router)
app.include_router(academic_router.public_router)
app.include_router(questions_router.router)
app.include_router(ai_router.inst_router)
app.include_router(ai_router.global_router)
app.include_router(exams_router.router)
app.include_router(attempts_router.router)
app.include_router(scoring_router.router)
app.include_router(scoring_router.student_router)
app.include_router(scoring_router.platform_router)
