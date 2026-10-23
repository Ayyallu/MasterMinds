"""Institution-Admin academic administration + public provisioning endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.dependencies import require_institution_admin
from app.models import (
    AcademicYear,
    ClassGroup,
    Course,
    Department,
    GradeLevel,
    Term,
)
from app.schemas import CurrentUser
from app.schemas_academic import (
    AcademicYearCreate,
    ClassGroupCreate,
    CourseCreate,
    DepartmentCreate,
    EnrollmentCreate,
    EnrollmentTransfer,
    GradeLevelCreate,
    InvitationAccept,
    InvitationCreate,
    MembershipApprove,
    RosterError,
    RosterRequest,
    RosterResult,
    StudentSelfRegister,
    TeacherAssignmentCreate,
    TermCreate,
)
from app.services import academic_service, roster_service
from app.services.auth_service import AuthError

settings = get_settings()

# --- Institution-scoped admin routes ---
router = APIRouter(prefix="/institutions/{institution_id}", tags=["academic"])


def _err(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _create(session, factory_coro):
    try:
        obj = await factory_coro
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"id": obj.id}


@router.post("/academic-years", status_code=201)
async def add_academic_year(
    institution_id: int,
    payload: AcademicYearCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    return await _create(
        session, academic_service.create_academic_year(session, institution_id, payload)
    )


@router.get("/academic-years")
async def list_academic_years(
    institution_id: int,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    rows = await academic_service.list_rows(session, AcademicYear, institution_id)
    return [{"id": r.id, "name": r.name, "is_current": r.is_current} for r in rows]


@router.post("/terms", status_code=201)
async def add_term(
    institution_id: int,
    payload: TermCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    return await _create(
        session, academic_service.create_term(session, institution_id, payload)
    )


@router.post("/grade-levels", status_code=201)
async def add_grade_level(
    institution_id: int,
    payload: GradeLevelCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    return await _create(
        session, academic_service.create_grade_level(session, institution_id, payload)
    )


@router.post("/departments", status_code=201)
async def add_department(
    institution_id: int,
    payload: DepartmentCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    return await _create(
        session, academic_service.create_department(session, institution_id, payload)
    )


@router.post("/courses", status_code=201)
async def add_course(
    institution_id: int,
    payload: CourseCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    return await _create(
        session, academic_service.create_course(session, institution_id, payload)
    )


@router.post("/class-groups", status_code=201)
async def add_class_group(
    institution_id: int,
    payload: ClassGroupCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    return await _create(
        session, academic_service.create_class_group(session, institution_id, payload)
    )


@router.get("/class-groups")
async def list_class_groups(
    institution_id: int,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    rows = await academic_service.list_rows(session, ClassGroup, institution_id)
    return [{"id": r.id, "name": r.name, "kind": r.kind} for r in rows]


@router.post("/invitations", status_code=201)
async def create_invitation(
    institution_id: int,
    payload: InvitationCreate,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        inv, raw = await academic_service.create_invitation(
            session, institution_id, current.id, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    result = {"id": inv.id, "role": inv.role, "status": inv.status}
    if not settings.is_production:
        result["debug_invitation_token"] = raw
    return result


@router.post("/memberships/approve", status_code=200)
async def approve_membership(
    institution_id: int,
    payload: MembershipApprove,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        m = await academic_service.approve_membership(
            session, institution_id, current.id, payload.user_id
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"user_id": m.user_id, "status": m.status}


@router.post("/teacher-assignments", status_code=201)
async def assign_teacher(
    institution_id: int,
    payload: TeacherAssignmentCreate,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        obj = await academic_service.assign_teacher(
            session, institution_id, current.id, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"id": obj.id}


@router.post("/enrollments", status_code=201)
async def enroll(
    institution_id: int,
    payload: EnrollmentCreate,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        obj = await academic_service.enroll_student(
            session, institution_id, current.id, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"id": obj.id, "status": obj.status}


@router.post("/enrollments/transfer", status_code=201)
async def transfer(
    institution_id: int,
    payload: EnrollmentTransfer,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        obj = await academic_service.transfer_enrollment(
            session, institution_id, current.id, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"id": obj.id, "status": obj.status}


@router.post("/roster/import", response_model=RosterResult)
async def roster_import(
    institution_id: int,
    payload: RosterRequest,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
) -> RosterResult:
    record = await roster_service.process_roster(
        session,
        institution_id=institution_id,
        actor_id=current.id,
        csv_text=payload.csv_text,
        class_group_code=payload.class_group_code,
        commit=payload.commit,
    )
    await session.commit()
    return RosterResult(
        import_id=record.id,
        status=record.status,
        total_rows=record.total_rows,
        valid_rows=record.valid_rows,
        error_rows=record.error_rows,
        errors=[RosterError(**e) for e in (record.errors or [])],
        committed=record.status == "committed",
    )


# --- Public provisioning routes (no institution path / no auth) ---
public_router = APIRouter(tags=["provisioning"])


@public_router.post("/invitations/accept", status_code=201)
async def accept_invitation(
    payload: InvitationAccept, session: AsyncSession = Depends(get_session)
):
    try:
        user = await academic_service.accept_invitation(session, payload)
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"user_id": user.id}


@public_router.post("/students/self-register", status_code=201)
async def student_self_register(
    payload: StudentSelfRegister, session: AsyncSession = Depends(get_session)
):
    try:
        user = await academic_service.student_self_register(session, payload)
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"user_id": user.id, "status": "pending_admin_approval"}
