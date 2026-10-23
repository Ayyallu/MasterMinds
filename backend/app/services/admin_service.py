"""Super-Admin platform operations: institution onboarding & provisioning."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Institution,
    InstitutionRegistrationRequest,
    InstitutionStatus,
    RequestStatus,
    RoleName,
)
from app.security import generate_opaque_token
from app.services import provisioning
from app.services.auth_service import AuthError, record_audit


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_registration(
    session: AsyncSession,
    *,
    institution_name: str,
    requested_code: str,
    contact_name: str,
    contact_email: str,
) -> InstitutionRegistrationRequest:
    req = InstitutionRegistrationRequest(
        institution_name=institution_name,
        requested_code=requested_code,
        contact_name=contact_name,
        contact_email=contact_email,
        status=RequestStatus.pending.value,
    )
    session.add(req)
    await session.flush()
    return req


async def list_registrations(
    session: AsyncSession, status: str | None = None
) -> list[InstitutionRegistrationRequest]:
    stmt = select(InstitutionRegistrationRequest)
    if status:
        stmt = stmt.where(InstitutionRegistrationRequest.status == status)
    res = await session.execute(stmt.order_by(InstitutionRegistrationRequest.id))
    return list(res.scalars().all())


async def approve_registration(
    session: AsyncSession,
    *,
    request_id: int,
    approver_id: int,
    admin_email: str,
    admin_full_name: str,
    admin_password: str | None,
) -> tuple[Institution, str | None]:
    req = await session.get(InstitutionRegistrationRequest, request_id)
    if req is None:
        raise AuthError("Registration request not found", status_code=404)
    if req.status != RequestStatus.pending.value:
        raise AuthError("Request already decided", status_code=409)

    # Institution code must be unique.
    exists = await session.execute(
        select(Institution).where(Institution.code == req.requested_code)
    )
    if exists.scalar_one_or_none() is not None:
        raise AuthError("Institution code already in use", status_code=409)

    institution = Institution(
        name=req.institution_name,
        code=req.requested_code,
        status=InstitutionStatus.active.value,
    )
    session.add(institution)
    await session.flush()

    # Provision the Institution Admin account.
    if await provisioning.get_user_by_email(session, admin_email) is not None:
        raise AuthError("Admin email already in use", status_code=409)
    temp_password = admin_password or generate_opaque_token()[:16]
    admin = await provisioning.create_user(
        session,
        email=admin_email,
        full_name=admin_full_name,
        password=temp_password,
    )
    await provisioning.grant_role(
        session, admin.id, RoleName.institution_admin, institution.id
    )
    await provisioning.ensure_membership(session, admin.id, institution.id)

    req.status = RequestStatus.approved.value
    req.decided_by_user_id = approver_id
    req.decided_at = _utcnow()
    req.created_institution_id = institution.id

    await record_audit(
        session,
        "institution.approved",
        actor_user_id=approver_id,
        institution_id=institution.id,
        target=req.requested_code,
    )
    # Return generated temp password only when the caller did not set one.
    return institution, (None if admin_password else temp_password)


async def reject_registration(
    session: AsyncSession, *, request_id: int, approver_id: int, reason: str
) -> None:
    req = await session.get(InstitutionRegistrationRequest, request_id)
    if req is None:
        raise AuthError("Registration request not found", status_code=404)
    if req.status != RequestStatus.pending.value:
        raise AuthError("Request already decided", status_code=409)
    req.status = RequestStatus.rejected.value
    req.reason = reason
    req.decided_by_user_id = approver_id
    req.decided_at = _utcnow()
    await record_audit(
        session,
        "institution.rejected",
        actor_user_id=approver_id,
        target=req.requested_code,
    )


async def set_institution_status(
    session: AsyncSession, *, institution_id: int, status: str, actor_id: int
) -> Institution:
    institution = await session.get(Institution, institution_id)
    if institution is None:
        raise AuthError("Institution not found", status_code=404)
    institution.status = status
    await record_audit(
        session,
        "institution.status_changed",
        actor_user_id=actor_id,
        institution_id=institution_id,
        detail={"status": status},
    )
    return institution
