"""Phase 7 endpoints: student exam delivery and reliable attempts."""
from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import get_current_user
from app.models import (
    Enrollment, EnrollmentStatus, Exam, ExamAttempt, ExamStatus,
    Institution, InstitutionMembership, Role, RoleName, UserRole, UserStatus,
)
from app.schemas import CurrentUser
from app.schemas_attempts import AnswerIn, AnswerSaved
from app.services import attempt_service
from app.services.auth_service import AuthError

router = APIRouter(tags=["attempts"])


def _err(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _require_student(current: CurrentUser) -> None:
    if "student" not in current.roles:
        raise HTTPException(status_code=403, detail="Student access required")


@router.post("/exams/{exam_id}/attempts/start")
async def start_attempt(
    exam_id: int,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _require_student(current)
    try:
        attempt = await attempt_service.start_or_resume(session, current, exam_id)
    except AuthError as exc:
        raise _err(exc)
    out = await attempt_service.build_output(session, attempt)
    await session.commit()
    return out


@router.get("/attempts/{attempt_id}")
async def get_attempt(
    attempt_id: int,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _require_student(current)
    try:
        attempt = await attempt_service.get_view(session, current, attempt_id)
    except AuthError as exc:
        raise _err(exc)
    out = await attempt_service.build_output(session, attempt)
    await session.commit()  # persist any auto-finalize on expiry
    return out


@router.put("/attempts/{attempt_id}/answers/{question_version_id}", response_model=AnswerSaved)
async def save_answer(
    attempt_id: int,
    question_version_id: int,
    payload: AnswerIn,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AnswerSaved:
    _require_student(current)
    try:
        row = await attempt_service.save_answer(
            session, current, attempt_id, question_version_id, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return AnswerSaved(
        question_version_id=question_version_id, answer_version=row.answer_version
    )


@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(
    attempt_id: int,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    _require_student(current)
    try:
        attempt = await attempt_service.submit(session, current, attempt_id)
    except AuthError as exc:
        raise _err(exc)
    out = await attempt_service.build_output(session, attempt)
    await session.commit()
    return out


@router.get("/student/exams")
async def list_student_exams(
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """List only exams belonging to institutions where the caller is an active student."""
    student_role_rows = await session.execute(
        select(UserRole.institution_id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserRole.user_id == current.id,
            Role.name == RoleName.student.value,
            UserRole.institution_id.is_not(None),
        )
    )
    student_institution_ids = {row[0] for row in student_role_rows.all()}
    if not student_institution_ids:
        raise HTTPException(status_code=403, detail="Student access required")

    membership_rows = await session.execute(
        select(InstitutionMembership.institution_id).where(
            InstitutionMembership.user_id == current.id,
            InstitutionMembership.institution_id.in_(student_institution_ids),
            InstitutionMembership.status == UserStatus.active.value,
        )
    )
    institution_ids = {row[0] for row in membership_rows.all()}
    if not institution_ids:
        return []

    exam_rows = await session.execute(
        select(Exam)
        .where(
            Exam.institution_id.in_(institution_ids),
            Exam.status.in_([
                ExamStatus.scheduled.value,
                ExamStatus.live.value,
                ExamStatus.closed.value,
                ExamStatus.results_pending.value,
                ExamStatus.published.value,
                ExamStatus.archived.value,
            ]),
        )
        .order_by(Exam.start_at.desc(), Exam.id.desc())
    )
    exams = list(exam_rows.scalars().all())
    output = []
    now = datetime.now(timezone.utc)
    for exam in exams:
        if exam.class_group_id is not None:
            enrollment = await session.execute(
                select(Enrollment.id).where(
                    Enrollment.student_user_id == current.id,
                    Enrollment.institution_id == exam.institution_id,
                    Enrollment.class_group_id == exam.class_group_id,
                    Enrollment.status == EnrollmentStatus.active.value,
                ).limit(1)
            )
            if enrollment.scalar() is None:
                continue

        attempts_result = await session.execute(
            select(ExamAttempt)
            .where(
                ExamAttempt.exam_id == exam.id,
                ExamAttempt.student_user_id == current.id,
            )
            .order_by(ExamAttempt.attempt_no)
        )
        attempts = list(attempts_result.scalars().all())
        institution = await session.get(Institution, exam.institution_id)
        output.append({
            "id": exam.id,
            "institution_id": exam.institution_id,
            "institution_name": institution.name if institution else "Institution",
            "title": exam.title,
            "status": exam.status,
            "start_at": exam.start_at,
            "end_at": exam.end_at,
            "duration_minutes": exam.duration_minutes,
            "attempt_limit": exam.attempt_limit,
            "results_published": exam.results_published,
            "can_start": (
                exam.status in (ExamStatus.scheduled.value, ExamStatus.live.value)
                and (exam.start_at is None or ((exam.start_at if exam.start_at.tzinfo else exam.start_at.replace(tzinfo=timezone.utc)) <= now))
                and (exam.end_at is None or ((exam.end_at if exam.end_at.tzinfo else exam.end_at.replace(tzinfo=timezone.utc)) >= now))
                and len(attempts) < exam.attempt_limit
            ),
            "attempts": [{
                "id": attempt.id,
                "attempt_no": attempt.attempt_no,
                "status": attempt.status,
                "started_at": attempt.started_at,
                "submitted_at": attempt.submitted_at,
            } for attempt in attempts],
        })
    return output
