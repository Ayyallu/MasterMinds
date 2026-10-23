"""Phase 7 endpoints: student exam delivery and reliable attempts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import get_current_user
from app.schemas import CurrentUser
from app.schemas_attempts import AnswerIn, AnswerSaved
from app.services import attempt_service
from app.services.auth_service import AuthError

router = APIRouter(tags=["attempts"])


def _err(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post("/exams/{exam_id}/attempts/start")
async def start_attempt(
    exam_id: int,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
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
    try:
        attempt = await attempt_service.submit(session, current, attempt_id)
    except AuthError as exc:
        raise _err(exc)
    out = await attempt_service.build_output(session, attempt)
    await session.commit()
    return out
