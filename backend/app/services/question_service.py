"""Question-bank domain: immutable versions, review gates, answer-key secrecy."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Question,
    QuestionOption,
    QuestionStatus,
    QuestionType,
    QuestionVersion,
)
from app.services.auth_service import AuthError, record_audit

# Upper bound on rows returned by a single search call (hardening).
MAX_SEARCH_ROWS = 2000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _apply_version_fields(v: QuestionVersion, data) -> None:
    v.type = data.type.value
    v.text = data.text
    v.explanation = data.explanation
    v.difficulty = data.difficulty.value
    v.marks = data.marks
    v.course_id = data.course_id
    v.topic_id = data.topic_id
    v.objective_id = data.objective_id
    v.grade_level_id = data.grade_level_id
    v.term_id = data.term_id
    v.source = data.source
    v.numerical_answer = data.numerical_answer
    v.numerical_tolerance = data.numerical_tolerance


def _add_options(session: AsyncSession, v: QuestionVersion, data) -> None:
    for idx, opt in enumerate(data.options):
        session.add(
            QuestionOption(
                version=v,
                text=opt.text,
                is_correct=opt.is_correct,
                order_index=idx,
            )
        )


async def create_question(
    session: AsyncSession, institution_id: int, actor_id: int, data
) -> QuestionVersion:
    question = Question(
        institution_id=institution_id,
        is_global=False,
        created_by_user_id=actor_id,
    )
    session.add(question)
    await session.flush()

    version = QuestionVersion(
        question_id=question.id,
        version_no=1,
        status=QuestionStatus.draft.value,
        created_by_user_id=actor_id,
    )
    _apply_version_fields(version, data)
    session.add(version)
    await session.flush()
    _add_options(session, version, data)
    await record_audit(
        session,
        "question.created",
        actor_user_id=actor_id,
        institution_id=institution_id,
        target=str(question.id),
    )
    await session.flush()
    return version


async def _load_question(
    session: AsyncSession, institution_id: int, question_id: int
) -> Question:
    q = await session.get(Question, question_id)
    if q is None or q.institution_id != institution_id:
        raise AuthError("Question not in this institution", 404)
    return q


async def add_version(
    session: AsyncSession, institution_id: int, question_id: int, actor_id: int, data
) -> QuestionVersion:
    """Editing creates a new immutable version; prior versions are untouched."""
    await _load_question(session, institution_id, question_id)
    res = await session.execute(
        select(QuestionVersion.version_no)
        .where(QuestionVersion.question_id == question_id)
        .order_by(QuestionVersion.version_no.desc())
    )
    last = res.scalars().first() or 0
    version = QuestionVersion(
        question_id=question_id,
        version_no=last + 1,
        status=QuestionStatus.draft.value,
        created_by_user_id=actor_id,
    )
    _apply_version_fields(version, data)
    session.add(version)
    await session.flush()
    _add_options(session, version, data)
    await record_audit(
        session,
        "question.version_added",
        actor_user_id=actor_id,
        institution_id=institution_id,
        target=str(question_id),
        detail={"version_no": version.version_no},
    )
    await session.flush()
    return version


async def _get_version(
    session: AsyncSession, institution_id: int, version_id: int
) -> QuestionVersion:
    v = await session.get(QuestionVersion, version_id)
    if v is None:
        raise AuthError("Version not found", 404)
    await _load_question(session, institution_id, v.question_id)
    return v


async def submit_for_review(
    session: AsyncSession, institution_id: int, version_id: int, actor_id: int
) -> QuestionVersion:
    v = await _get_version(session, institution_id, version_id)
    if v.status not in (QuestionStatus.draft.value, QuestionStatus.rejected.value):
        raise AuthError("Only draft/rejected versions can be submitted", 400)
    v.status = QuestionStatus.in_review.value
    return v


async def review_version(
    session: AsyncSession,
    institution_id: int,
    version_id: int,
    reviewer_id: int,
    approve: bool,
) -> QuestionVersion:
    v = await _get_version(session, institution_id, version_id)
    if v.status != QuestionStatus.in_review.value:
        raise AuthError("Version is not awaiting review", 400)
    if approve:
        v.status = QuestionStatus.approved.value
        v.approved_by_user_id = reviewer_id
        v.approved_at = _utcnow()
    else:
        v.status = QuestionStatus.rejected.value
    await record_audit(
        session,
        "question.reviewed",
        actor_user_id=reviewer_id,
        institution_id=institution_id,
        target=str(v.question_id),
        detail={"version_id": version_id, "approved": approve},
    )
    return v


async def review_global_version(
    session: AsyncSession, version_id: int, reviewer_id: int, approve: bool
) -> QuestionVersion:
    """Central Academic Reviewer gate for the platform-global shared library."""
    v = await session.get(QuestionVersion, version_id)
    if v is None:
        raise AuthError("Version not found", 404)
    q = await session.get(Question, v.question_id)
    if q is None or not q.is_global:
        raise AuthError("Not a global question", 400)
    if v.status != QuestionStatus.in_review.value:
        raise AuthError("Version is not awaiting review", 400)
    if approve:
        v.status = QuestionStatus.approved.value
        v.approved_by_user_id = reviewer_id
        v.approved_at = _utcnow()
    else:
        v.status = QuestionStatus.rejected.value
    await record_audit(
        session,
        "global_question.reviewed",
        actor_user_id=reviewer_id,
        target=str(v.question_id),
        detail={"version_id": version_id, "approved": approve},
    )
    return v


async def search_global(
    session: AsyncSession, filters, *, can_review: bool = False
) -> list[QuestionVersion]:
    """Search global questions without exposing tenant-private content.

    Only central reviewers may select non-approved workflow states. All other
    callers are restricted to approved versions, regardless of the status
    submitted in their request.
    """
    stmt = (
        select(QuestionVersion)
        .join(Question, Question.id == QuestionVersion.question_id)
        .where(
            Question.is_global.is_(True),
            Question.withdrawn.is_(False),
        )
    )
    if can_review:
        if filters.status is not None:
            stmt = stmt.where(QuestionVersion.status == filters.status)
    else:
        stmt = stmt.where(QuestionVersion.status == QuestionStatus.approved.value)
    if filters.type is not None:
        stmt = stmt.where(QuestionVersion.type == filters.type.value)
    if filters.difficulty is not None:
        stmt = stmt.where(QuestionVersion.difficulty == filters.difficulty.value)
    res = await session.execute(
        stmt.order_by(QuestionVersion.id).limit(MAX_SEARCH_ROWS)
    )
    return list(res.scalars().all())


async def list_versions(
    session: AsyncSession, institution_id: int, question_id: int
) -> list[QuestionVersion]:
    await _load_question(session, institution_id, question_id)
    res = await session.execute(
        select(QuestionVersion)
        .where(QuestionVersion.question_id == question_id)
        .order_by(QuestionVersion.version_no)
    )
    return list(res.scalars().all())


async def search(
    session: AsyncSession, institution_id: int, filters
) -> list[QuestionVersion]:
    stmt = (
        select(QuestionVersion)
        .join(Question, Question.id == QuestionVersion.question_id)
        .where(Question.institution_id == institution_id, Question.withdrawn.is_(False))
    )
    if filters.course_id is not None:
        stmt = stmt.where(QuestionVersion.course_id == filters.course_id)
    if filters.grade_level_id is not None:
        stmt = stmt.where(QuestionVersion.grade_level_id == filters.grade_level_id)
    if filters.term_id is not None:
        stmt = stmt.where(QuestionVersion.term_id == filters.term_id)
    if filters.topic_id is not None:
        stmt = stmt.where(QuestionVersion.topic_id == filters.topic_id)
    if filters.objective_id is not None:
        stmt = stmt.where(QuestionVersion.objective_id == filters.objective_id)
    if filters.type is not None:
        stmt = stmt.where(QuestionVersion.type == filters.type.value)
    if filters.difficulty is not None:
        stmt = stmt.where(QuestionVersion.difficulty == filters.difficulty.value)
    if filters.status is not None:
        stmt = stmt.where(QuestionVersion.status == filters.status)
    # Bound result sets so a large question bank cannot be dumped in one call.
    res = await session.execute(stmt.order_by(QuestionVersion.id).limit(MAX_SEARCH_ROWS))
    return list(res.scalars().all())


async def load_options(
    session: AsyncSession, version_id: int
) -> list[QuestionOption]:
    res = await session.execute(
        select(QuestionOption)
        .where(QuestionOption.question_version_id == version_id)
        .order_by(QuestionOption.order_index)
    )
    return list(res.scalars().all())


def serialize(
    version: QuestionVersion, options: list[QuestionOption], *, include_keys: bool
) -> dict:
    """Serialize a version. With include_keys=False (student-facing) the answer
    key is omitted entirely — correct flags and numerical answers never leak."""
    data = {
        "question_id": version.question_id,
        "version_id": version.id,
        "version_no": version.version_no,
        "type": version.type,
        "text": version.text,
        "explanation": version.explanation if include_keys else None,
        "difficulty": version.difficulty,
        "marks": version.marks,
        "status": version.status,
        "options": [
            {
                "id": o.id,
                "text": o.text,
                "order_index": o.order_index,
                "is_correct": o.is_correct if include_keys else None,
            }
            for o in options
        ],
        "numerical_answer": version.numerical_answer if include_keys else None,
        "numerical_tolerance": version.numerical_tolerance if include_keys else None,
    }
    return data
