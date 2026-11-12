"""Institution-Admin operations: academic structure, provisioning, enrollment."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AcademicYear,
    ClassGroup,
    Course,
    Department,
    Enrollment,
    EnrollmentStatus,
    GradeLevel,
    Institution,
    InstitutionMembership,
    InstitutionStatus,
    Invitation,
    InvitationStatus,
    RoleName,
    Term,
    TeacherAssignment,
    User,
    UserRole,
    UserStatus,
)
from app.security import generate_opaque_token, hash_token
from app.services import provisioning
from app.services.auth_service import AuthError, record_audit

VALID_INVITE_ROLES = {RoleName.teacher.value, RoleName.student.value}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- Academic structure ---
async def create_academic_year(session, institution_id, data) -> AcademicYear:
    obj = AcademicYear(
        institution_id=institution_id,
        name=data.name,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
    )
    session.add(obj)
    await session.flush()
    return obj


async def create_term(session, institution_id, data) -> Term:
    year = await session.get(AcademicYear, data.academic_year_id)
    if year is None or year.institution_id != institution_id:
        raise AuthError("Academic year not in this institution", status_code=404)
    obj = Term(
        institution_id=institution_id,
        academic_year_id=data.academic_year_id,
        name=data.name,
        sequence=data.sequence,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    session.add(obj)
    await session.flush()
    return obj


async def create_grade_level(session, institution_id, data) -> GradeLevel:
    obj = GradeLevel(
        institution_id=institution_id,
        name=data.name,
        kind=data.kind,
        sequence=data.sequence,
    )
    session.add(obj)
    await session.flush()
    return obj


async def create_department(session, institution_id, data) -> Department:
    obj = Department(institution_id=institution_id, name=data.name, code=data.code)
    session.add(obj)
    await session.flush()
    return obj


async def create_course(session, institution_id, data) -> Course:
    if data.department_id is not None:
        dept = await session.get(Department, data.department_id)
        if dept is None or dept.institution_id != institution_id:
            raise AuthError("Department not in this institution", status_code=404)
    obj = Course(
        institution_id=institution_id,
        department_id=data.department_id,
        name=data.name,
        code=data.code,
    )
    session.add(obj)
    await session.flush()
    return obj


async def create_class_group(session, institution_id, data) -> ClassGroup:
    await _check_tenant_refs(session, ClassGroup, institution_id, data.model_dump())
    obj = ClassGroup(
        institution_id=institution_id,
        name=data.name,
        kind=data.kind,
        grade_level_id=data.grade_level_id,
        term_id=data.term_id,
        course_id=data.course_id,
    )
    session.add(obj)
    await session.flush()
    return obj


async def list_rows(session: AsyncSession, model, institution_id: int) -> list:
    res = await session.execute(
        select(model).where(model.institution_id == institution_id).order_by(model.id)
    )
    return list(res.scalars().all())


def row_dict(obj) -> dict:
    """Serialize a row's columns (minus the tenant id) for list views."""
    out = {}
    for col in obj.__table__.columns:
        if col.name == "institution_id":
            continue
        val = getattr(obj, col.name)
        out[col.name] = val.isoformat() if hasattr(val, "isoformat") else val
    return out


# Foreign keys that must stay inside the same institution when edited.
_TENANT_REFS = {
    Term: {"academic_year_id": AcademicYear},
    Course: {"department_id": Department},
    ClassGroup: {
        "grade_level_id": GradeLevel,
        "term_id": Term,
        "course_id": Course,
    },
}


async def _get_owned(session: AsyncSession, model, institution_id: int, obj_id: int):
    obj = await session.get(model, obj_id)
    if obj is None or obj.institution_id != institution_id:
        raise AuthError("Not found", 404)
    return obj


async def _check_tenant_refs(
    session: AsyncSession, model, institution_id: int, values: dict
) -> None:
    """Every linked row (term, grade, course…) must exist in the SAME institution."""
    for field, ref_model in _TENANT_REFS.get(model, {}).items():
        ref_id = values.get(field)
        if ref_id is not None:
            ref = await session.get(ref_model, ref_id)
            if ref is None or ref.institution_id != institution_id:
                raise AuthError(f"{ref_model.__name__} not in this institution", 404)


async def _usage(session: AsyncSession, obj) -> list[str]:
    """Describe rows in OTHER tables that reference `obj` via a foreign key.

    The schema uses ON DELETE CASCADE / SET NULL on several of these links
    (e.g. enrollments -> class_groups), so letting the delete through would
    silently destroy or detach history. Callers refuse the delete instead.
    """
    table = obj.__table__
    found: list[str] = []
    for other in table.metadata.sorted_tables:
        for fk in other.foreign_keys:
            if fk.column.table is not table:
                continue
            count = await session.scalar(
                select(func.count()).select_from(other).where(fk.parent == obj.id)
            )
            if count:
                label = other.name.replace("_", " ")
                found.append(f"{count} {label}")
    return found


async def update_row(
    session: AsyncSession, model, institution_id: int, obj_id: int, values: dict
):
    obj = await _get_owned(session, model, institution_id, obj_id)
    await _check_tenant_refs(session, model, institution_id, values)
    for field, val in values.items():
        setattr(obj, field, val)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise AuthError("Another record already uses these values", 409)
    return obj


async def delete_row(
    session: AsyncSession, model, institution_id: int, obj_id: int
) -> None:
    obj = await _get_owned(session, model, institution_id, obj_id)
    in_use = await _usage(session, obj)
    if in_use:
        raise AuthError(
            "Cannot delete: still used by " + ", ".join(in_use)
            + ". Remove or reassign those first.",
            409,
        )
    try:
        await session.delete(obj)
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise AuthError("This record is in use and cannot be deleted", 409)


# --- Provisioning: invitations ---
async def create_invitation(
    session: AsyncSession, institution_id: int, actor_id: int, data
) -> tuple[Invitation, str]:
    if data.role not in VALID_INVITE_ROLES:
        raise AuthError("Invitations are limited to teacher or student", 400)
    raw = generate_opaque_token()
    inv = Invitation(
        institution_id=institution_id,
        email=data.email.lower() if data.email else None,
        role=data.role,
        register_number=data.register_number,
        token_hash=hash_token(raw),
        status=InvitationStatus.pending.value,
        expires_at=_utcnow() + timedelta(days=14),
        created_by_user_id=actor_id,
    )
    session.add(inv)
    await record_audit(
        session,
        "account.invited",
        actor_user_id=actor_id,
        institution_id=institution_id,
        detail={"role": data.role},
    )
    await session.flush()
    return inv, raw


async def accept_invitation(session: AsyncSession, data) -> User:
    res = await session.execute(
        select(Invitation).where(Invitation.token_hash == hash_token(data.token))
    )
    inv = res.scalar_one_or_none()
    if inv is None or inv.status != InvitationStatus.pending.value:
        raise AuthError("Invalid or used invitation", 400)
    inst = await session.get(Institution, inv.institution_id)
    if inst is None or inst.status != InstitutionStatus.active.value:
        raise AuthError("This institution is not currently active", 403)
    if _aware(inv.expires_at) < _utcnow():
        inv.status = InvitationStatus.expired.value
        raise AuthError("Invitation expired", 400)

    user = await provisioning.create_user(
        session,
        email=inv.email,
        full_name=data.full_name,
        password=data.password,
        status=UserStatus.active.value,
    )
    await provisioning.grant_role(
        session, user.id, RoleName(inv.role), inv.institution_id
    )
    await provisioning.ensure_membership(
        session,
        user.id,
        inv.institution_id,
        register_number=inv.register_number,
        status=UserStatus.active.value,
    )
    inv.status = InvitationStatus.accepted.value
    inv.accepted_user_id = user.id
    await record_audit(
        session,
        "account.invitation_accepted",
        actor_user_id=user.id,
        institution_id=inv.institution_id,
    )
    return user


# --- Student self-registration (pending admin approval) ---
async def student_self_register(session: AsyncSession, data) -> User:
    res = await session.execute(
        select(Institution).where(Institution.code == data.institution_code)
    )
    institution = res.scalar_one_or_none()
    if institution is None:
        raise AuthError("Unknown institution code", 404)
    if institution.status != InstitutionStatus.active.value:
        raise AuthError("This institution is not accepting registrations", 403)

    # Register number must be unique within the institution.
    dup = await session.execute(
        select(InstitutionMembership).where(
            InstitutionMembership.institution_id == institution.id,
            InstitutionMembership.register_number == data.register_number,
        )
    )
    if dup.scalar_one_or_none() is not None:
        raise AuthError("Register number already in use", 409)

    # Account and membership both stay pending until an Institution Admin
    # approves; a pending account cannot authenticate.
    user = await provisioning.create_user(
        session,
        email=data.email,
        full_name=data.full_name,
        password=data.password,
        status=UserStatus.pending.value,
    )
    await provisioning.grant_role(
        session, user.id, RoleName.student, institution.id
    )
    await provisioning.ensure_membership(
        session,
        user.id,
        institution.id,
        register_number=data.register_number,
        status=UserStatus.pending.value,
    )
    await record_audit(
        session,
        "student.self_registered",
        actor_user_id=user.id,
        institution_id=institution.id,
    )
    return user


async def approve_membership(
    session: AsyncSession, institution_id: int, actor_id: int, user_id: int
) -> InstitutionMembership:
    res = await session.execute(
        select(InstitutionMembership).where(
            InstitutionMembership.user_id == user_id,
            InstitutionMembership.institution_id == institution_id,
        )
    )
    membership = res.scalar_one_or_none()
    if membership is None:
        raise AuthError("Membership not found", 404)
    membership.status = UserStatus.active.value
    # Activate the account too, so an approved student can authenticate.
    student = await session.get(User, user_id)
    if student is not None and student.status == UserStatus.pending.value:
        student.status = UserStatus.active.value
    await record_audit(
        session,
        "student.membership_approved",
        actor_user_id=actor_id,
        institution_id=institution_id,
        target=str(user_id),
    )
    return membership


# --- Teacher assignments ---
async def assign_teacher(
    session: AsyncSession, institution_id: int, actor_id: int, data
) -> TeacherAssignment:
    cg = await session.get(ClassGroup, data.class_group_id)
    if cg is None or cg.institution_id != institution_id:
        raise AuthError("Class group not in this institution", 404)
    if not await _user_has_role(
        session, data.teacher_user_id, RoleName.teacher, institution_id
    ):
        raise AuthError("Target user is not a teacher in this institution", 400)
    obj = TeacherAssignment(
        institution_id=institution_id,
        teacher_user_id=data.teacher_user_id,
        class_group_id=data.class_group_id,
    )
    session.add(obj)
    await record_audit(
        session,
        "teacher.assigned",
        actor_user_id=actor_id,
        institution_id=institution_id,
        detail={"class_group_id": data.class_group_id},
    )
    await session.flush()
    return obj


async def _user_has_role(
    session: AsyncSession, user_id: int, role: RoleName, institution_id: int
) -> bool:
    role_id = await provisioning.get_role_id(session, role)
    res = await session.execute(
        select(UserRole.id).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.institution_id == institution_id,
        )
    )
    return res.scalar_one_or_none() is not None


# --- Enrollments (history preserved) ---
async def enroll_student(
    session: AsyncSession, institution_id: int, actor_id: int, data
) -> Enrollment:
    cg = await session.get(ClassGroup, data.class_group_id)
    if cg is None or cg.institution_id != institution_id:
        raise AuthError("Class group not in this institution", 404)
    if not await _user_has_role(
        session, data.student_user_id, RoleName.student, institution_id
    ):
        raise AuthError("Target user is not a student in this institution", 400)
    if data.term_id is not None:
        term = await session.get(Term, data.term_id)
        if term is None or term.institution_id != institution_id:
            raise AuthError("Term not in this institution", 404)
    existing = await session.scalar(
        select(Enrollment.id).where(
            Enrollment.student_user_id == data.student_user_id,
            Enrollment.class_group_id == data.class_group_id,
            Enrollment.status == EnrollmentStatus.active.value,
        ).limit(1)
    )
    if existing is not None:
        raise AuthError("Student is already enrolled in this class group", 409)
    obj = Enrollment(
        institution_id=institution_id,
        student_user_id=data.student_user_id,
        class_group_id=data.class_group_id,
        term_id=data.term_id,
        status=EnrollmentStatus.active.value,
    )
    session.add(obj)
    await record_audit(
        session,
        "student.enrolled",
        actor_user_id=actor_id,
        institution_id=institution_id,
        detail={"class_group_id": data.class_group_id},
    )
    await session.flush()
    return obj


async def transfer_enrollment(
    session: AsyncSession, institution_id: int, actor_id: int, data
) -> Enrollment:
    current = await session.get(Enrollment, data.enrollment_id)
    if current is None or current.institution_id != institution_id:
        raise AuthError("Enrollment not found", 404)
    if current.status != EnrollmentStatus.active.value:
        raise AuthError("Only an active enrollment can be transferred", 409)
    target = await session.get(ClassGroup, data.new_class_group_id)
    if target is None or target.institution_id != institution_id:
        raise AuthError("Class group not in this institution", 404)
    already = await session.scalar(
        select(Enrollment.id).where(
            Enrollment.student_user_id == current.student_user_id,
            Enrollment.class_group_id == target.id,
            Enrollment.status == EnrollmentStatus.active.value,
        ).limit(1)
    )
    if target.id == current.class_group_id or already is not None:
        raise AuthError("Student is already in this class group", 409)
    if data.term_id is not None:
        term = await session.get(Term, data.term_id)
        if term is None or term.institution_id != institution_id:
            raise AuthError("Term not in this institution", 404)
    # Preserve history: close the old enrollment, create a new one.
    current.status = EnrollmentStatus.transferred.value
    current.ended_at = _utcnow()
    new = Enrollment(
        institution_id=institution_id,
        student_user_id=current.student_user_id,
        class_group_id=data.new_class_group_id,
        term_id=data.term_id or current.term_id,
        status=EnrollmentStatus.active.value,
    )
    session.add(new)
    await record_audit(
        session,
        "student.transferred",
        actor_user_id=actor_id,
        institution_id=institution_id,
        detail={
            "from_class_group": current.class_group_id,
            "to_class_group": data.new_class_group_id,
        },
    )
    await session.flush()
    return new
