"""Phase 8 endpoints: scoring, result release, corrections and reporting."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import (
    get_current_user,
    require_institution_admin,
    require_institution_staff,
    require_super_admin,
)
from app.models import Exam, RoleName, TeacherAssignment
from app.schemas import CurrentUser
from app.schemas_scoring import CorrectionIn
from app.services import scoring_service
from app.services.auth_service import AuthError, record_audit

router = APIRouter(prefix="/institutions/{institution_id}", tags=["scoring"])


def _err(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/exams/{exam_id}/score")
async def score_exam(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        result = await scoring_service.score_exam(
            session, institution_id, exam_id, current.id
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return result


@router.post("/exams/{exam_id}/publish-results")
async def publish_results(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        exam = await scoring_service.publish_results(
            session, institution_id, exam_id, current.id
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"exam_id": exam.id, "results_published": exam.results_published}


@router.post("/attempts/{attempt_id}/correct")
async def correct_score(
    institution_id: int,
    attempt_id: int,
    payload: CorrectionIn,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        score = await scoring_service.correct_score(
            session, institution_id, attempt_id, current.id,
            payload.awarded_marks, payload.reason,
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"attempt_id": attempt_id, "awarded_marks": score.awarded_marks,
            "score_version": score.score_version}


async def _teacher_report_scope(
    session: AsyncSession, current: CurrentUser, institution_id: int, exam_id: int
) -> None:
    """Teachers may only report on exams for their assigned class groups."""
    if current.is_super_admin or RoleName.institution_admin.value in current.roles:
        return
    exam = await session.get(Exam, exam_id)
    if exam is None or exam.institution_id != institution_id:
        raise AuthError("Exam not found", 404)
    res = await session.execute(
        select(TeacherAssignment.id).where(
            TeacherAssignment.teacher_user_id == current.id,
            TeacherAssignment.class_group_id == exam.class_group_id,
        )
    )
    if res.scalar_one_or_none() is None:
        raise AuthError("Not authorized for this exam's report", 403)


@router.get("/exams/{exam_id}/report")
async def exam_report(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    try:
        await _teacher_report_scope(session, current, institution_id, exam_id)
        return await scoring_service.exam_report(session, institution_id, exam_id)
    except AuthError as exc:
        raise _err(exc)


@router.get("/exams/{exam_id}/report.csv", response_class=PlainTextResponse)
async def exam_report_csv(
    institution_id: int,
    exam_id: int,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    try:
        await _teacher_report_scope(session, current, institution_id, exam_id)
        report = await scoring_service.exam_report(session, institution_id, exam_id)
    except AuthError as exc:
        raise _err(exc)
    return PlainTextResponse(
        scoring_service.report_to_csv(report), media_type="text/csv"
    )


@router.get("/reports/enrollment")
async def enrollment_report(
    institution_id: int,
    census_date: date = Query(...),
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    return await scoring_service.enrollment_census(session, institution_id, census_date)


# --- Student result ---
student_router = APIRouter(tags=["results"])


@student_router.get("/attempts/{attempt_id}/result")
async def my_result(
    attempt_id: int,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if RoleName.student.value not in current.roles:
        raise HTTPException(status_code=403, detail="Student access required")
    try:
        return await scoring_service.student_result(session, current.id, attempt_id)
    except AuthError as exc:
        raise _err(exc)


# --- Super Admin platform report (audited cross-tenant) ---
platform_router = APIRouter(prefix="/admin", tags=["platform-reports"])


@platform_router.get("/institutions/{institution_id}/exams/{exam_id}/report")
async def platform_exam_report(
    institution_id: int,
    exam_id: int,
    request: Request,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        report = await scoring_service.exam_report(session, institution_id, exam_id)
    except AuthError as exc:
        raise _err(exc)
    await record_audit(
        session, "platform.exam_report_accessed", actor_user_id=current.id,
        institution_id=institution_id, target=str(exam_id),
        ip=request.client.host if request.client else None,
    )
    await session.commit()
    return report
