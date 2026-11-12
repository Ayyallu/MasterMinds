"""Deterministic scoring, result release, corrections and reporting."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttemptAnswer,
    AttemptScore,
    AttemptStatus,
    Enrollment,
    Exam,
    ExamAttempt,
    QuestionOption,
    QuestionVersion,
    ResultReleaseRule,
    ScoreHistory,
    User,
)
from app.services.auth_service import AuthError, record_audit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _numeric_match(student: str, answer: str, tol: str | None) -> bool:
    # Decimal (not float) so a tolerance boundary is exact: 3.13 vs 3.14 ± 0.01
    # must match. Binary floats make |3.13 - 3.14| slightly larger than 0.01.
    try:
        s, a = Decimal(str(student).strip()), Decimal(str(answer).strip())
        t = Decimal(str(tol).strip()) if tol not in (None, "") else Decimal(0)
        if not (s.is_finite() and a.is_finite() and t.is_finite()):
            return False
        return abs(s - a) <= abs(t)
    except (InvalidOperation, TypeError, ValueError):
        return str(student).strip() == str(answer).strip()


async def _score_question(
    session: AsyncSession, snap_q: dict, answer: dict | None, negative: bool
) -> dict:
    marks = snap_q["marks"]
    qtype = snap_q["type"]
    version = await session.get(QuestionVersion, snap_q["version_id"])

    if qtype == "numerical":
        student_val = (answer or {}).get("numerical_value")
        answered = student_val is not None and str(student_val) != ""
        correct = answered and _numeric_match(
            student_val, version.numerical_answer or "", version.numerical_tolerance
        )
    else:
        opt_res = await session.execute(
            select(QuestionOption).where(
                QuestionOption.question_version_id == snap_q["version_id"]
            )
        )
        correct_ids = {o.id for o in opt_res.scalars().all() if o.is_correct}
        selected = set((answer or {}).get("selected_option_ids", []))
        answered = bool(selected)
        # Single/true-false and multi-select all share exact-match semantics;
        # multi-select is all-or-nothing by default.
        correct = answered and selected == correct_ids

    if correct:
        awarded = marks
    elif answered and negative:
        awarded = -marks
    else:
        awarded = 0
    return {
        "version_id": snap_q["version_id"],
        "marks": marks,
        "awarded": awarded,
        "correct": bool(correct),
        "answered": bool(answered),
    }


async def score_attempt(
    session: AsyncSession,
    attempt: ExamAttempt,
    *,
    actor_id: int | None,
    reason: str | None = None,
) -> AttemptScore:
    negative = bool(attempt.snapshot.get("marking", {}).get("negative_marking"))
    answers_res = await session.execute(
        select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id)
    )
    answers = {a.question_version_id: a.answer for a in answers_res.scalars().all()}

    breakdown = []
    total = awarded = 0
    for snap_q in attempt.snapshot["questions"]:
        line = await _score_question(
            session, snap_q, answers.get(snap_q["version_id"]), negative
        )
        breakdown.append(line)
        total += line["marks"]
        awarded += line["awarded"]
    awarded = max(0, awarded)  # never below zero overall

    res = await session.execute(
        select(AttemptScore).where(AttemptScore.attempt_id == attempt.id)
    )
    score = res.scalar_one_or_none()
    if score is None:
        score = AttemptScore(
            attempt_id=attempt.id,
            exam_id=attempt.exam_id,
            institution_id=attempt.institution_id,
            student_user_id=attempt.student_user_id,
            total_marks=total,
            awarded_marks=awarded,
            score_version=1,
            breakdown=breakdown,
            scored_by_user_id=actor_id,
            scored_at=_utcnow(),
        )
        session.add(score)
    else:
        score.total_marks = total
        score.awarded_marks = awarded
        score.score_version += 1
        score.breakdown = breakdown
        score.scored_by_user_id = actor_id
        score.scored_at = _utcnow()

    session.add(
        ScoreHistory(
            attempt_id=attempt.id,
            score_version=score.score_version,
            total_marks=total,
            awarded_marks=awarded,
            breakdown=breakdown,
            reason=reason,
            scored_by_user_id=actor_id,
        )
    )
    await session.flush()
    return score


async def _load_exam(session: AsyncSession, institution_id: int, exam_id: int) -> Exam:
    exam = await session.get(Exam, exam_id)
    if exam is None or exam.institution_id != institution_id:
        raise AuthError("Exam not in this institution", 404)
    return exam


async def score_exam(
    session: AsyncSession, institution_id: int, exam_id: int, actor_id: int
) -> dict:
    exam = await _load_exam(session, institution_id, exam_id)
    if exam.results_published:
        raise AuthError(
            "Results already published; use a correction instead of re-scoring", 409
        )
    res = await session.execute(
        select(ExamAttempt).where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.status.in_(
                [AttemptStatus.submitted.value, AttemptStatus.expired.value]
            ),
        )
    )
    attempts = list(res.scalars().all())
    for a in attempts:
        await score_attempt(session, a, actor_id=actor_id)
    await record_audit(
        session, "exam.scored", actor_user_id=actor_id,
        institution_id=institution_id, target=str(exam_id),
        detail={"attempts": len(attempts)},
    )
    return {"scored_attempts": len(attempts)}


async def publish_results(
    session: AsyncSession, institution_id: int, exam_id: int, actor_id: int
) -> Exam:
    exam = await _load_exam(session, institution_id, exam_id)
    if exam.results_published:
        return exam  # idempotent
    if exam.result_release_rule == ResultReleaseRule.after_close.value:
        if not (exam.end_at and _utcnow() > _aware(exam.end_at)):
            raise AuthError(
                "Release rule is after_close; the exam window has not closed", 409
            )
    exam.results_published = True
    exam.results_published_by_user_id = actor_id
    exam.results_published_at = _utcnow()
    await record_audit(
        session, "results.published", actor_user_id=actor_id,
        institution_id=institution_id, target=str(exam_id),
    )
    return exam


async def correct_score(
    session: AsyncSession,
    institution_id: int,
    attempt_id: int,
    actor_id: int,
    awarded_marks: int,
    reason: str,
) -> AttemptScore:
    attempt = await session.get(ExamAttempt, attempt_id)
    if attempt is None or attempt.institution_id != institution_id:
        raise AuthError("Attempt not found", 404)
    res = await session.execute(
        select(AttemptScore).where(AttemptScore.attempt_id == attempt_id)
    )
    score = res.scalar_one_or_none()
    if score is None:
        raise AuthError("Attempt has not been scored yet", 409)
    if not 0 <= awarded_marks <= score.total_marks:
        raise AuthError(
            f"Corrected marks must be between 0 and {score.total_marks}", 400
        )
    score.awarded_marks = awarded_marks
    score.score_version += 1
    score.scored_by_user_id = actor_id
    score.scored_at = _utcnow()
    session.add(
        ScoreHistory(
            attempt_id=attempt_id,
            score_version=score.score_version,
            total_marks=score.total_marks,
            awarded_marks=awarded_marks,
            breakdown=score.breakdown,
            reason=reason,
            scored_by_user_id=actor_id,
        )
    )
    await record_audit(
        session, "score.corrected", actor_user_id=actor_id,
        institution_id=institution_id, target=str(attempt_id),
        detail={"awarded": awarded_marks, "reason": reason},
    )
    await session.flush()
    return score


async def student_result(
    session: AsyncSession, student_id: int, attempt_id: int
) -> dict:
    attempt = await session.get(ExamAttempt, attempt_id)
    if attempt is None or attempt.student_user_id != student_id:
        raise AuthError("Attempt not found", 404)
    exam = await session.get(Exam, attempt.exam_id)
    if not exam.results_published:
        raise AuthError("Results are not released yet", 403)
    res = await session.execute(
        select(AttemptScore).where(AttemptScore.attempt_id == attempt_id)
    )
    score = res.scalar_one_or_none()
    if score is None:
        raise AuthError("No score available", 404)
    # Per-question outcome only — never the correct answer or explanation.
    questions = [
        {"version_id": b["version_id"], "marks": b["marks"],
         "awarded": b["awarded"], "correct": b["correct"]}
        for b in (score.breakdown or [])
    ]
    return {
        "attempt_id": attempt_id,
        "exam_id": attempt.exam_id,
        "total_marks": score.total_marks,
        "awarded_marks": score.awarded_marks,
        "questions": questions,
    }


async def exam_report(
    session: AsyncSession, institution_id: int, exam_id: int
) -> dict:
    await _load_exam(session, institution_id, exam_id)
    att_res = await session.execute(
        select(ExamAttempt).where(ExamAttempt.exam_id == exam_id)
    )
    attempts = list(att_res.scalars().all())
    score_res = await session.execute(
        select(AttemptScore).where(AttemptScore.exam_id == exam_id)
    )
    scores = {s.attempt_id: s for s in score_res.scalars().all()}

    rows = []
    for a in attempts:
        s = scores.get(a.id)
        rows.append(
            {
                "student_user_id": a.student_user_id,
                "status": a.status,
                "awarded_marks": s.awarded_marks if s else None,
                "total_marks": s.total_marks if s else None,
            }
        )
    completed = sum(
        1 for a in attempts
        if a.status in (AttemptStatus.submitted.value, AttemptStatus.expired.value)
    )
    distribution = [r["awarded_marks"] for r in rows if r["awarded_marks"] is not None]
    return {
        "exam_id": exam_id,
        "participants": len(attempts),
        "completed": completed,
        "score_distribution": distribution,
        "rows": rows,
    }


def report_to_csv(report: dict) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["student_user_id", "status", "awarded_marks", "total_marks"])
    for r in report["rows"]:
        writer.writerow(
            [r["student_user_id"], r["status"], r["awarded_marks"], r["total_marks"]]
        )
    return buf.getvalue()


async def enrollment_census(
    session: AsyncSession, institution_id: int, census: date
) -> dict:
    """Census rule: an enrollment counts if it began on/before the census date
    and had not ended before it (ended_at is null or after the census date)."""
    res = await session.execute(
        select(Enrollment).where(Enrollment.institution_id == institution_id)
    )
    count = 0
    for e in res.scalars().all():
        started = _aware(e.created_at).date()
        ended = _aware(e.ended_at).date() if e.ended_at else None
        if started <= census and (ended is None or ended > census):
            count += 1
    return {"institution_id": institution_id, "census_date": census.isoformat(),
            "active_enrollments": count}
