"""Phase 5 endpoints: AI question generation and the global shared library."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import rate_limit
from app.ai.base import GenerationSpec, ProviderNotConfigured
from app.ai.factory import get_provider
from app.config import get_settings
from app.db import get_session
from app.dependencies import (
    require_central_reviewer,
    require_institution_staff,
    require_roles,
)
from app.models import GenerationJob, RoleName
from app.schemas import CurrentUser
from app.schemas_ai import GenerationJobOut, GenerationRequest
from app.schemas_questions import QuestionSearch
from app.services import generation_service, question_service
from app.services.auth_service import AuthError

settings = get_settings()


def _job_out(job: GenerationJob) -> GenerationJobOut:
    return GenerationJobOut(
        id=job.id,
        status=job.status,
        provider=job.provider,
        model=job.model,
        is_global=job.is_global,
        requested_count=job.requested_count,
        stored_count=job.stored_count,
        rejected_count=job.rejected_count,
        duplicate_count=job.duplicate_count,
        error=job.error,
        usage=job.usage,
    )


def _rate_check(user_id: int) -> None:
    key = f"ai:{user_id}"
    if rate_limit.is_limited(
        key,
        settings.ai_generation_max_per_window,
        settings.ai_generation_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI generation rate limit reached; try again later.",
        )


def _spec(payload: GenerationRequest) -> GenerationSpec:
    return GenerationSpec(
        question_type=payload.question_type.value,
        count=payload.count,
        difficulty=payload.difficulty.value,
        subject=payload.subject,
        topics=payload.topics,
        grade=payload.grade,
    )


# --- Institution-private generation ---
inst_router = APIRouter(prefix="/institutions/{institution_id}", tags=["ai"])


@inst_router.post("/ai/generate", response_model=GenerationJobOut, status_code=201)
async def generate_private(
    institution_id: int,
    payload: GenerationRequest,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
) -> GenerationJobOut:
    _rate_check(current.id)
    try:
        provider = get_provider()
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    try:
        job = await generation_service.run_generation(
            session,
            provider=provider,
            institution_id=institution_id,
            is_global=False,
            actor_id=current.id,
            spec=_spec(payload),
            idempotency_key=payload.idempotency_key,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return _job_out(job)


@inst_router.get("/ai/jobs/{job_id}", response_model=GenerationJobOut)
async def get_job(
    institution_id: int,
    job_id: int,
    _: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
) -> GenerationJobOut:
    job = await session.get(GenerationJob, job_id)
    if job is None or job.institution_id != institution_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job)


# --- Global shared library ---
global_router = APIRouter(prefix="/global", tags=["global-library"])


@global_router.post("/ai/generate", response_model=GenerationJobOut, status_code=201)
async def generate_global(
    payload: GenerationRequest,
    current: CurrentUser = Depends(require_central_reviewer()),
    session: AsyncSession = Depends(get_session),
) -> GenerationJobOut:
    _rate_check(current.id)
    try:
        provider = get_provider()
    except ProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    job = await generation_service.run_generation(
        session,
        provider=provider,
        institution_id=None,
        is_global=True,
        actor_id=current.id,
        spec=_spec(payload),
        idempotency_key=payload.idempotency_key,
    )
    await session.commit()
    return _job_out(job)


@global_router.post("/questions/versions/{version_id}/review")
async def review_global(
    version_id: int,
    approve: bool,
    current: CurrentUser = Depends(require_central_reviewer()),
    session: AsyncSession = Depends(get_session),
):
    try:
        v = await question_service.review_global_version(
            session, version_id, current.id, approve
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return {"version_id": v.id, "status": v.status}


@global_router.post("/library/search")
async def search_global_library(
    filters: QuestionSearch,
    _: CurrentUser = Depends(
        require_roles(
            RoleName.institution_admin,
            RoleName.teacher,
            RoleName.central_academic_reviewer,
        )
    ),
    session: AsyncSession = Depends(get_session),
):
    versions = await question_service.search_global(session, filters)
    out = []
    for v in versions:
        opts = await question_service.load_options(session, v.id)
        out.append(question_service.serialize(v, opts, include_keys=True))
    return out
