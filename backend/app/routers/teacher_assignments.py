"""Exam authoring helper endpoints for institution-scoped class groups."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_institution_staff
from app.models import ClassGroup, RoleName, TeacherAssignment
from app.schemas import CurrentUser

router = APIRouter(
    prefix="/institutions/{institution_id}",
    tags=["academic"],
)


@router.get("/class-groups/available-for-exam")
async def available_class_groups(
    institution_id: int,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Return all class groups for admins and assigned groups for teachers."""
    stmt = select(ClassGroup).where(ClassGroup.institution_id == institution_id)
    is_admin = current.is_super_admin or (
        RoleName.institution_admin.value in current.roles
    )
    if not is_admin:
        stmt = (
            stmt.join(
                TeacherAssignment,
                TeacherAssignment.class_group_id == ClassGroup.id,
            )
            .where(
                TeacherAssignment.institution_id == institution_id,
                TeacherAssignment.teacher_user_id == current.id,
            )
        )
    result = await session.execute(stmt.order_by(ClassGroup.name))
    return [{"id": group.id, "name": group.name} for group in result.scalars()]
