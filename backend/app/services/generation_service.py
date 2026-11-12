"""Pre-exam AI question generation: validate, dedupe, store for human review."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import (
    GenerationSpec,
    ProviderAuthError,
    ProviderError,
    QuestionProvider,
)
from app.config import get_settings
from app.models import (
    GenerationJob,
    GenerationStatus,
    Question,
    QuestionOption,
    QuestionStatus,
    QuestionVersion,
)
from app.schemas_questions import QuestionCreate
from app.services.auth_service import AuthError, record_audit

_settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


async def _existing_texts(
    session: AsyncSession, institution_id: int | None, is_global: bool
) -> set[str]:
    stmt = select(QuestionVersion.text).join(
        Question, Question.id == QuestionVersion.question_id
    )
    if is_global:
        stmt = stmt.where(Question.is_global.is_(True))
    else:
        stmt = stmt.where(Question.institution_id == institution_id)
    res = await session.execute(stmt)
    return {_normalize(t) for (t,) in res.all()}


async def run_generation(
    session: AsyncSession,
    *,
    provider: QuestionProvider,
    institution_id: int | None,
    is_global: bool,
    actor_id: int,
    spec: GenerationSpec,
    idempotency_key: str | None = None,
) -> GenerationJob:
    if spec.count < 1 or spec.count > _settings.ai_max_pool_size:
        raise AuthError(
            f"Pool size must be between 1 and {_settings.ai_max_pool_size}", 400
        )

    # Idempotency: a repeated submit with the same key returns the first job.
    if idempotency_key:
        existing = await session.execute(
            select(GenerationJob).where(
                GenerationJob.idempotency_key == idempotency_key
            )
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            return prior

    job = GenerationJob(
        institution_id=institution_id,
        is_global=is_global,
        requested_by_user_id=actor_id,
        provider=provider.name,
        status=GenerationStatus.running.value,
        params={
            "type": spec.question_type,
            "count": spec.count,
            "difficulty": spec.difficulty,
            "subject": spec.subject,
            "topics": spec.topics,
            "grade": spec.grade,
        },
        idempotency_key=idempotency_key,
        requested_count=spec.count,
    )
    session.add(job)
    await session.flush()

    # Call the provider with bounded retries on transient failures.
    result = None
    last_error: Exception | None = None
    for attempt in range(_settings.ai_retry_max + 1):
        try:
            result = await provider.generate(spec)
            break
        except ProviderAuthError as exc:
            # Bad key / unavailable model: retrying cannot succeed.
            last_error = exc
            break
        except ProviderError as exc:
            last_error = exc
            if attempt < _settings.ai_retry_max:
                await asyncio.sleep(0.5 * (attempt + 1))  # short backoff
            continue

    if result is None:
        job.status = GenerationStatus.failed.value
        # Provider messages are written to be secret-free and actionable.
        job.error = (str(last_error) or type(last_error).__name__)[:500]
        job.finished_at = _utcnow()
        await record_audit(
            session,
            "ai.generation_failed",
            actor_user_id=actor_id,
            institution_id=institution_id,
            detail={"provider": provider.name},
        )
        await session.flush()
        return job

    seen = await _existing_texts(session, institution_id, is_global)
    stored = rejected = duplicate = 0

    for raw in result.candidates:
        try:
            validated = QuestionCreate(**raw)
        except (ValidationError, TypeError):
            rejected += 1
            continue
        norm = _normalize(validated.text)
        if norm in seen:
            duplicate += 1
            continue
        seen.add(norm)
        await _store_candidate(
            session,
            institution_id=institution_id,
            is_global=is_global,
            actor_id=actor_id,
            data=validated,
            provider_name=provider.name,
            model=result.model,
            job_id=job.id,
        )
        stored += 1

    job.model = result.model
    job.status = GenerationStatus.completed.value
    job.stored_count = stored
    job.rejected_count = rejected
    job.duplicate_count = duplicate
    # Usage/cost metadata only — never secrets or full prompts.
    job.usage = result.usage or None
    job.finished_at = _utcnow()
    await record_audit(
        session,
        "ai.generation_completed",
        actor_user_id=actor_id,
        institution_id=institution_id,
        detail={"stored": stored, "rejected": rejected, "duplicate": duplicate},
    )
    await session.flush()
    return job


async def _store_candidate(
    session: AsyncSession,
    *,
    institution_id: int | None,
    is_global: bool,
    actor_id: int,
    data: QuestionCreate,
    provider_name: str,
    model: str,
    job_id: int,
) -> None:
    question = Question(
        institution_id=None if is_global else institution_id,
        is_global=is_global,
        created_by_user_id=actor_id,
    )
    session.add(question)
    await session.flush()

    version = QuestionVersion(
        question_id=question.id,
        version_no=1,
        type=data.type.value,
        text=data.text,
        explanation=data.explanation,
        difficulty=data.difficulty.value,
        marks=data.marks,
        course_id=data.course_id,
        topic_id=data.topic_id,
        objective_id=data.objective_id,
        grade_level_id=data.grade_level_id,
        term_id=data.term_id,
        numerical_answer=data.numerical_answer,
        numerical_tolerance=data.numerical_tolerance,
        source=f"ai:{provider_name}:{model}",
        # Candidates always require human review before use.
        status=QuestionStatus.in_review.value,
        created_by_user_id=actor_id,
        generation_job_id=job_id,
    )
    session.add(version)
    await session.flush()
    for idx, opt in enumerate(data.options):
        session.add(
            QuestionOption(
                question_version_id=version.id,
                text=opt.text,
                is_correct=opt.is_correct,
                order_index=idx,
            )
        )
