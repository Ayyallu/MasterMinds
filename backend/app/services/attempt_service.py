"""Student attempt engine: snapshots, autosave, server-authoritative timing."""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttemptAnswer,
    AttemptStatus,
    Enrollment,
    EnrollmentStatus,
    Exam,
    ExamAttempt,
    ExamQuestion,
    ExamStatus,
    InstitutionMembership,
    QuestionOption,
    QuestionVersion,
    UserStatus,
)
from app.schemas import CurrentUser
from app.services.auth_service import AuthError, record_audit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def _eligible(
    session: AsyncSession, current: CurrentUser, exam: Exam
) -> None:
    res = await session.execute(
        select(InstitutionMembership).where(
            InstitutionMembership.user_id == current.id,
            InstitutionMembership.institution_id == exam.institution_id,
            InstitutionMembership.status == UserStatus.active.value,
        )
    )
    if res.scalar_one_or_none() is None:
        raise AuthError("Not eligible for this exam", 403)
    if exam.class_group_id is not None:
        enr = await session.execute(
            select(Enrollment).where(
                Enrollment.student_user_id == current.id,
                Enrollment.class_group_id == exam.class_group_id,
                Enrollment.status == EnrollmentStatus.active.value,
            )
        )
        if enr.scalar_one_or_none() is None:
            raise AuthError("Not enrolled in this exam's class", 403)


def _available(exam: Exam, now: datetime) -> None:
    if exam.status not in (ExamStatus.scheduled.value, ExamStatus.live.value):
        raise AuthError("Exam is not open", 409)
    if exam.start_at and now < _aware(exam.start_at):
        raise AuthError("Exam has not started", 409)
    if exam.end_at and now > _aware(exam.end_at):
        raise AuthError("Exam window has closed", 409)


async def _build_snapshot(session: AsyncSession, exam: Exam) -> dict:
    res = await session.execute(
        select(ExamQuestion)
        .where(ExamQuestion.exam_id == exam.id)
        .order_by(ExamQuestion.order_index)
    )
    eqs = list(res.scalars().all())
    rng = random.Random()
    if exam.randomize:
        rng.shuffle(eqs)

    questions = []
    for eq in eqs:
        v = await session.get(QuestionVersion, eq.question_version_id)
        opts = await session.execute(
            select(QuestionOption.id)
            .where(QuestionOption.question_version_id == v.id)
            .order_by(QuestionOption.order_index)
        )
        option_ids = [o for (o,) in opts.all()]
        if exam.randomize:
            rng.shuffle(option_ids)
        questions.append(
            {
                "version_id": v.id,
                "type": v.type,
                "marks": v.marks,
                "option_order": option_ids,
            }
        )
    return {
        "randomize": exam.randomize,
        "duration_minutes": exam.duration_minutes,
        "marking": {"negative_marking": exam.negative_marking},
        "questions": questions,
    }


def _finalize_if_expired(attempt, now: datetime) -> None:
    if attempt.status == AttemptStatus.in_progress.value and now > _aware(
        attempt.deadline_at
    ):
        attempt.status = AttemptStatus.submitted.value
        attempt.auto_submitted = True
        attempt.submitted_at = _aware(attempt.deadline_at)


async def start_or_resume(
    session: AsyncSession, current: CurrentUser, exam_id: int
):
    exam = await session.get(Exam, exam_id)
    if exam is None:
        raise AuthError("Exam not found", 404)
    await _eligible(session, current, exam)
    now = _utcnow()

    # Resume an existing in-progress attempt (same snapshot) if present.
    existing = await session.execute(
        select(ExamAttempt)
        .where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.student_user_id == current.id,
        )
        .order_by(ExamAttempt.attempt_no.desc())
    )
    attempts = list(existing.scalars().all())
    for a in attempts:
        _finalize_if_expired(a, now)
    in_progress = next(
        (a for a in attempts if a.status == AttemptStatus.in_progress.value), None
    )
    if in_progress is not None:
        return in_progress

    # New attempt — enforce availability and attempt limit.
    _available(exam, now)
    if len(attempts) >= exam.attempt_limit:
        raise AuthError("Attempt limit reached", 403)

    snapshot = await _build_snapshot(session, exam)
    deadline = now + timedelta(minutes=exam.duration_minutes)
    if exam.end_at and _aware(exam.end_at) < deadline:
        deadline = _aware(exam.end_at)

    attempt = ExamAttempt(
        exam_id=exam_id,
        institution_id=exam.institution_id,
        student_user_id=current.id,
        attempt_no=len(attempts) + 1,
        status=AttemptStatus.in_progress.value,
        snapshot=snapshot,
        started_at=now,
        deadline_at=deadline,
    )
    session.add(attempt)
    await record_audit(
        session, "attempt.started", actor_user_id=current.id,
        institution_id=exam.institution_id, target=str(exam_id),
    )
    await session.flush()
    return attempt


async def _load_owned_attempt(
    session: AsyncSession, current: CurrentUser, attempt_id: int
):
    attempt = await session.get(ExamAttempt, attempt_id)
    if attempt is None or attempt.student_user_id != current.id:
        raise AuthError("Attempt not found", 404)
    return attempt


async def get_view(session: AsyncSession, current: CurrentUser, attempt_id: int):
    attempt = await _load_owned_attempt(session, current, attempt_id)
    _finalize_if_expired(attempt, _utcnow())
    return attempt


async def save_answer(
    session: AsyncSession,
    current: CurrentUser,
    attempt_id: int,
    question_version_id: int,
    answer_in,
):
    attempt = await _load_owned_attempt(session, current, attempt_id)
    _finalize_if_expired(attempt, _utcnow())
    if attempt.status != AttemptStatus.in_progress.value:
        raise AuthError("Attempt is no longer open for answers", 409)

    snap_q = next(
        (q for q in attempt.snapshot["questions"] if q["version_id"] == question_version_id),
        None,
    )
    if snap_q is None:
        raise AuthError("Question not part of this attempt", 400)

    payload = _validate_answer(snap_q, answer_in)

    res = await session.execute(
        select(AttemptAnswer).where(
            AttemptAnswer.attempt_id == attempt_id,
            AttemptAnswer.question_version_id == question_version_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        row = AttemptAnswer(
            attempt_id=attempt_id,
            question_version_id=question_version_id,
            answer=payload,
            answer_version=1,
        )
        session.add(row)
    else:
        # Idempotent/concurrent-safe: last write wins, version advances.
        row.answer = payload
        row.answer_version += 1
    await session.flush()
    return row


def _validate_answer(snap_q: dict, answer_in) -> dict:
    if snap_q["type"] == "numerical":
        if answer_in.numerical_value is None:
            raise AuthError("numerical_value required", 400)
        return {"numerical_value": str(answer_in.numerical_value)}
    allowed = set(snap_q["option_order"])
    selected = answer_in.selected_option_ids or []
    for oid in selected:
        if oid not in allowed:
            raise AuthError("Selected option is not part of this question", 400)
    if snap_q["type"] == "single_mcq" and len(selected) > 1:
        raise AuthError("Single-answer question allows one selection", 400)
    return {"selected_option_ids": selected}


async def submit(session: AsyncSession, current: CurrentUser, attempt_id: int):
    attempt = await _load_owned_attempt(session, current, attempt_id)
    now = _utcnow()
    _finalize_if_expired(attempt, now)
    # Idempotent: a completed attempt returns unchanged, never duplicated.
    if attempt.status != AttemptStatus.in_progress.value:
        return attempt
    attempt.status = AttemptStatus.submitted.value
    attempt.submitted_at = now
    await record_audit(
        session, "attempt.submitted", actor_user_id=current.id,
        institution_id=attempt.institution_id, target=str(attempt.exam_id),
    )
    return attempt


async def build_output(session: AsyncSession, attempt) -> dict:
    """Assemble the student-facing attempt view. Answer keys are never included."""
    answers_res = await session.execute(
        select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)
    )
    saved = {a.question_version_id: a.answer for a in answers_res.scalars().all()}

    questions = []
    for q in attempt.snapshot["questions"]:
        v = await session.get(QuestionVersion, q["version_id"])
        opt_rows = await session.execute(
            select(QuestionOption).where(
                QuestionOption.question_version_id == q["version_id"]
            )
        )
        by_id = {o.id: o for o in opt_rows.scalars().all()}
        options = [
            {"id": oid, "text": by_id[oid].text}
            for oid in q["option_order"]
            if oid in by_id
        ]
        questions.append(
            {
                "question_version_id": q["version_id"],
                "type": q["type"],
                "text": v.text,
                "marks": q["marks"],
                "options": options,
                "answer": saved.get(q["version_id"]),
            }
        )

    now = _utcnow()
    remaining = max(0, int((_aware(attempt.deadline_at) - now).total_seconds()))
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "status": attempt.status,
        "attempt_no": attempt.attempt_no,
        "started_at": attempt.started_at,
        "deadline_at": attempt.deadline_at,
        "submitted_at": attempt.submitted_at,
        "seconds_remaining": remaining if attempt.status == "in_progress" else 0,
        "questions": questions,
    }
