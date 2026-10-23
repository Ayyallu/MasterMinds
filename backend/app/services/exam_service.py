"""Exam authoring: lifecycle state machine, selection, approval freeze."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Exam,
    ExamQuestion,
    ExamStatus,
    Question,
    QuestionStatus,
    QuestionVersion,
    RoleName,
    TeacherAssignment,
)
from app.schemas import CurrentUser
from app.services.auth_service import AuthError, record_audit

# Server-enforced lifecycle transitions.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ExamStatus.draft.value: {ExamStatus.awaiting_approval.value, ExamStatus.cancelled.value},
    ExamStatus.awaiting_approval.value: {
        ExamStatus.approved.value,
        ExamStatus.draft.value,
        ExamStatus.cancelled.value,
    },
    ExamStatus.approved.value: {
        ExamStatus.scheduled.value,
        ExamStatus.draft.value,
        ExamStatus.cancelled.value,
    },
    ExamStatus.scheduled.value: {
        ExamStatus.draft.value,
        ExamStatus.live.value,
        ExamStatus.cancelled.value,
    },
    ExamStatus.live.value: {ExamStatus.closed.value},
    ExamStatus.closed.value: {ExamStatus.results_pending.value},
    ExamStatus.results_pending.value: {ExamStatus.published.value},
    ExamStatus.published.value: {ExamStatus.archived.value},
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_transition(exam: Exam, new_status: str) -> None:
    allowed = ALLOWED_TRANSITIONS.get(exam.status, set())
    if new_status not in allowed:
        raise AuthError(
            f"Invalid transition {exam.status} -> {new_status}", 409
        )


def _is_admin(current: CurrentUser) -> bool:
    return current.is_super_admin or RoleName.institution_admin.value in current.roles


async def _check_author_scope(
    session: AsyncSession,
    current: CurrentUser,
    institution_id: int,
    class_group_id: int | None,
) -> None:
    """Teachers may author only within classes they are assigned to."""
    if _is_admin(current):
        return
    if RoleName.teacher.value not in current.roles:
        raise AuthError("Not permitted to author exams", 403)
    if class_group_id is None:
        raise AuthError("Teachers must target an assigned class group", 400)
    res = await session.execute(
        select(TeacherAssignment.id).where(
            TeacherAssignment.institution_id == institution_id,
            TeacherAssignment.teacher_user_id == current.id,
            TeacherAssignment.class_group_id == class_group_id,
        )
    )
    if res.scalar_one_or_none() is None:
        raise AuthError("You are not assigned to this class group", 403)


async def _load_exam(session: AsyncSession, institution_id: int, exam_id: int) -> Exam:
    exam = await session.get(Exam, exam_id)
    if exam is None or exam.institution_id != institution_id:
        raise AuthError("Exam not in this institution", 404)
    return exam


def _apply(exam: Exam, data) -> None:
    exam.title = data.title
    exam.course_id = data.course_id
    exam.grade_level_id = data.grade_level_id
    exam.term_id = data.term_id
    exam.class_group_id = data.class_group_id
    exam.duration_minutes = data.duration_minutes
    exam.attempt_limit = data.attempt_limit
    exam.distribution = [r.model_dump(mode="json") for r in data.distribution]
    exam.randomize = data.randomize
    exam.late_entry_minutes = data.late_entry_minutes
    exam.negative_marking = data.negative_marking
    exam.result_release_rule = data.result_release_rule.value
    exam.timezone = data.timezone
    exam.start_at = data.start_at
    exam.end_at = data.end_at


async def create_exam(
    session: AsyncSession, institution_id: int, current: CurrentUser, data
) -> Exam:
    await _check_author_scope(session, current, institution_id, data.class_group_id)
    exam = Exam(
        institution_id=institution_id,
        created_by_user_id=current.id,
        status=ExamStatus.draft.value,
    )
    _apply(exam, data)
    session.add(exam)
    await record_audit(
        session, "exam.created", actor_user_id=current.id,
        institution_id=institution_id, target=data.title,
    )
    await session.flush()
    return exam


async def update_exam(
    session: AsyncSession, institution_id: int, exam_id: int, current: CurrentUser, data
) -> Exam:
    exam = await _load_exam(session, institution_id, exam_id)
    if exam.status != ExamStatus.draft.value:
        raise AuthError("Only draft exams can be edited; reopen to change", 409)
    await _check_author_scope(session, current, institution_id, data.class_group_id)
    _apply(exam, data)
    await record_audit(
        session, "exam.updated", actor_user_id=current.id,
        institution_id=institution_id, target=str(exam_id),
    )
    return exam


async def submit_for_approval(
    session: AsyncSession, institution_id: int, exam_id: int, current: CurrentUser
) -> Exam:
    exam = await _load_exam(session, institution_id, exam_id)
    await _check_author_scope(session, current, institution_id, exam.class_group_id)
    _require_transition(exam, ExamStatus.awaiting_approval.value)
    if not exam.distribution:
        raise AuthError("Blueprint distribution is required before submission", 400)
    exam.status = ExamStatus.awaiting_approval.value
    await record_audit(
        session, "exam.submitted", actor_user_id=current.id,
        institution_id=institution_id, target=str(exam_id),
    )
    return exam


async def _eligible_versions(
    session: AsyncSession, institution_id: int, rule: dict
) -> list[QuestionVersion]:
    stmt = (
        select(QuestionVersion)
        .join(Question, Question.id == QuestionVersion.question_id)
        .where(
            QuestionVersion.status == QuestionStatus.approved.value,
            Question.withdrawn.is_(False),
            # Approved private (this institution) OR approved global. Prefer
            # the institution's own first; global fills the rest.
            (Question.institution_id == institution_id) | (Question.is_global.is_(True)),
        )
    )
    if rule.get("type"):
        stmt = stmt.where(QuestionVersion.type == rule["type"])
    if rule.get("difficulty"):
        stmt = stmt.where(QuestionVersion.difficulty == rule["difficulty"])
    if rule.get("topic_id"):
        stmt = stmt.where(QuestionVersion.topic_id == rule["topic_id"])
    # Institution-owned first (is_global False sorts before True).
    stmt = stmt.order_by(Question.is_global, QuestionVersion.id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def approve(
    session: AsyncSession, institution_id: int, exam_id: int, admin: CurrentUser
) -> Exam:
    exam = await _load_exam(session, institution_id, exam_id)
    _require_transition(exam, ExamStatus.approved.value)

    # Select an approved pool satisfying the blueprint; block on insufficiency.
    selected: list[int] = []
    used: set[int] = set()
    total_marks = 0
    shortfalls: list[dict] = []
    for rule in exam.distribution or []:
        eligible = await _eligible_versions(session, institution_id, rule)
        available = [v for v in eligible if v.id not in used]
        need = rule["count"]
        if len(available) < need:
            shortfalls.append(
                {"rule": rule, "needed": need, "available": len(available)}
            )
            continue
        for v in available[:need]:
            used.add(v.id)
            selected.append(v.id)
            total_marks += v.marks

    if shortfalls:
        raise AuthError(
            f"Approved question pool cannot satisfy the blueprint: {shortfalls}", 400
        )

    # Pin the selected versions.
    await session.execute(delete(ExamQuestion).where(ExamQuestion.exam_id == exam_id))
    for idx, vid in enumerate(selected):
        session.add(
            ExamQuestion(exam_id=exam_id, question_version_id=vid, order_index=idx)
        )

    exam.num_questions = len(selected)
    exam.status = ExamStatus.approved.value
    exam.frozen = True
    exam.approved_by_user_id = admin.id
    exam.approved_at = _utcnow()
    exam.frozen_snapshot = {
        "title": exam.title,
        "distribution": exam.distribution,
        "duration_minutes": exam.duration_minutes,
        "attempt_limit": exam.attempt_limit,
        "randomize": exam.randomize,
        "negative_marking": exam.negative_marking,
        "result_release_rule": exam.result_release_rule,
        "total_marks": total_marks,
        "question_version_ids": selected,
    }
    await record_audit(
        session, "exam.approved", actor_user_id=admin.id,
        institution_id=institution_id, target=str(exam_id),
        detail={"num_questions": len(selected), "total_marks": total_marks},
    )
    return exam


async def reject(
    session: AsyncSession, institution_id: int, exam_id: int, admin: CurrentUser
) -> Exam:
    exam = await _load_exam(session, institution_id, exam_id)
    _require_transition(exam, ExamStatus.draft.value)
    exam.status = ExamStatus.draft.value
    await record_audit(
        session, "exam.rejected", actor_user_id=admin.id,
        institution_id=institution_id, target=str(exam_id),
    )
    return exam


async def schedule(
    session: AsyncSession, institution_id: int, exam_id: int, admin: CurrentUser, data
) -> Exam:
    exam = await _load_exam(session, institution_id, exam_id)
    _require_transition(exam, ExamStatus.scheduled.value)
    exam.start_at = data.start_at
    exam.end_at = data.end_at
    exam.timezone = data.timezone
    exam.status = ExamStatus.scheduled.value
    await record_audit(
        session, "exam.scheduled", actor_user_id=admin.id,
        institution_id=institution_id, target=str(exam_id),
    )
    return exam


async def reopen(
    session: AsyncSession, institution_id: int, exam_id: int, admin: CurrentUser
) -> Exam:
    """Material change after approval requires renewed approval."""
    exam = await _load_exam(session, institution_id, exam_id)
    if exam.status not in (ExamStatus.approved.value, ExamStatus.scheduled.value):
        raise AuthError("Only approved/scheduled exams can be reopened", 409)
    await session.execute(delete(ExamQuestion).where(ExamQuestion.exam_id == exam_id))
    exam.status = ExamStatus.draft.value
    exam.frozen = False
    exam.frozen_snapshot = None
    exam.approved_by_user_id = None
    exam.approved_at = None
    exam.num_questions = 0
    await record_audit(
        session, "exam.reopened", actor_user_id=admin.id,
        institution_id=institution_id, target=str(exam_id),
    )
    return exam


async def get_exam(
    session: AsyncSession, institution_id: int, exam_id: int
) -> Exam:
    return await _load_exam(session, institution_id, exam_id)


async def preview_questions(
    session: AsyncSession, institution_id: int, exam_id: int
) -> list[dict]:
    """Staff preview — answer keys are NOT included (student-safe)."""
    from app.services import question_service

    await _load_exam(session, institution_id, exam_id)
    res = await session.execute(
        select(ExamQuestion)
        .where(ExamQuestion.exam_id == exam_id)
        .order_by(ExamQuestion.order_index)
    )
    out = []
    for eq in res.scalars().all():
        v = await session.get(QuestionVersion, eq.question_version_id)
        opts = await question_service.load_options(session, v.id)
        out.append(question_service.serialize(v, opts, include_keys=False))
    return out
