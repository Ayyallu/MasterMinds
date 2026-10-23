"""Phase 6 endpoints: exam authoring, blueprint, approval and scheduling."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_institution_admin, require_institution_staff
from app.models import Exam
from app.schemas import CurrentUser
from app.schemas_exams import ExamCreate, ExamOut, ScheduleIn
from app.services import exam_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/institutions/{institution_id}/exams", tags=["exams"])


def _out(exam: Exam) -> ExamOut:
    return ExamOut(
        id=exam.id,
        title=exam.title,
        status=exam.status,
        num_questions=exam.num_questions,
        duration_minutes=exam.duration_minutes,
        attempt_limit=exam.attempt_limit,
        randomize=exam.randomize,
        result_release_rule=exam.result_release_rule,
        frozen=exam.frozen,
        start_at=exam.start_at,
        end_at=exam.end_at,
        timezone=exam.timezone,
    )


def _err(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("", response_model=ExamOut, status_code=201)
async def create_exam(
    institution_id: int,
    payload: ExamCreate,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.create_exam(session, institution_id, current, payload)
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return _out(exam)


@router.put("/{exam_id}", response_model=ExamOut)
async def update_exam(
    institution_id: int,
    exam_id: int,
    payload: ExamCreate,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.update_exam(
            session, institution_id, exam_id, current, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return _out(exam)


@router.post("/{exam_id}/submit", response_model=ExamOut)
async def submit(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.submit_for_approval(
            session, institution_id, exam_id, current
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return _out(exam)


@router.post("/{exam_id}/approve", response_model=ExamOut)
async def approve(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.approve(session, institution_id, exam_id, current)
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return _out(exam)


@router.post("/{exam_id}/reject", response_model=ExamOut)
async def reject(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.reject(session, institution_id, exam_id, current)
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return _out(exam)


@router.post("/{exam_id}/schedule", response_model=ExamOut)
async def schedule(
    institution_id: int,
    exam_id: int,
    payload: ScheduleIn,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.schedule(
            session, institution_id, exam_id, current, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return _out(exam)


@router.post("/{exam_id}/reopen", response_model=ExamOut)
async def reopen(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.reopen(session, institution_id, exam_id, current)
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return _out(exam)


@router.get("/{exam_id}", response_model=ExamOut)
async def get_exam(
    institution_id: int,
    exam_id: int,
    _: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
) -> ExamOut:
    try:
        exam = await exam_service.get_exam(session, institution_id, exam_id)
    except AuthError as exc:
        raise _err(exc)
    return _out(exam)


@router.get("/{exam_id}/preview")
async def preview(
    institution_id: int,
    exam_id: int,
    _: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await exam_service.preview_questions(session, institution_id, exam_id)
    except AuthError as exc:
        raise _err(exc)
