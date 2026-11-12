"""Super-Admin platform endpoints: institution onboarding."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.dependencies import (
    enforce_tenant_scope,
    get_current_user,
    require_institution_admin,
    require_super_admin,
)
from app.models import InstitutionStatus
from app.schemas import CurrentUser
from app.schemas_academic import (
    InstitutionOut,
    RegistrationApprove,
    RegistrationCreate,
    RegistrationOut,
    RegistrationReject,
)
from app.schemas_institution import (
    InstitutionCreate,
    InstitutionProfileIn,
    InstitutionProfileOut,
)
from app.services import admin_service
from app.services.auth_service import AuthError

router = APIRouter(tags=["platform"])
_settings = get_settings()


@router.post("/registrations", response_model=RegistrationOut, status_code=201)
async def submit_registration(
    payload: RegistrationCreate, session: AsyncSession = Depends(get_session)
) -> RegistrationOut:
    """Public: an institution requests to join. Super Admin approval required."""
    req = await admin_service.create_registration(
        session,
        institution_name=payload.institution_name,
        requested_code=payload.requested_code,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
    )
    await session.commit()
    return RegistrationOut(
        id=req.id,
        institution_name=req.institution_name,
        requested_code=req.requested_code,
        contact_name=req.contact_name,
        contact_email=req.contact_email,
        status=req.status,
    )


@router.get("/admin/registrations", response_model=list[RegistrationOut])
async def list_registrations(
    status_filter: str | None = None,
    _: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> list[RegistrationOut]:
    rows = await admin_service.list_registrations(session, status_filter)
    return [
        RegistrationOut(
            id=r.id,
            institution_name=r.institution_name,
            requested_code=r.requested_code,
            contact_name=r.contact_name,
            contact_email=r.contact_email,
            status=r.status,
        )
        for r in rows
    ]


@router.post("/admin/registrations/{request_id}/approve")
async def approve_registration(
    request_id: int,
    payload: RegistrationApprove,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        institution, temp_password = await admin_service.approve_registration(
            session,
            request_id=request_id,
            approver_id=current.id,
            admin_email=payload.admin_email,
            admin_full_name=payload.admin_full_name,
            admin_password=payload.admin_password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    result: dict = {
        "institution": InstitutionOut(
            id=institution.id,
            name=institution.name,
            code=institution.code,
            status=institution.status,
        ).model_dump(),
        "admin_email": payload.admin_email,
    }
    # Dev convenience: surface the generated temp password when none was set.
    if not _settings.is_production and temp_password:
        result["debug_admin_temp_password"] = temp_password
    return result


@router.post(
    "/admin/registrations/{request_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reject_registration(
    request_id: int,
    payload: RegistrationReject,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
):
    from fastapi import Response

    try:
        await admin_service.reject_registration(
            session,
            request_id=request_id,
            approver_id=current.id,
            reason=payload.reason,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/institutions/{institution_id}/disable")
async def disable_institution(
    institution_id: int,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> InstitutionOut:
    try:
        inst = await admin_service.set_institution_status(
            session,
            institution_id=institution_id,
            status=InstitutionStatus.disabled.value,
            actor_id=current.id,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return InstitutionOut(id=inst.id, name=inst.name, code=inst.code, status=inst.status)


@router.post("/admin/institutions/{institution_id}/enable")
async def enable_institution(
    institution_id: int,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> InstitutionOut:
    try:
        inst = await admin_service.set_institution_status(
            session,
            institution_id=institution_id,
            status=InstitutionStatus.active.value,
            actor_id=current.id,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return InstitutionOut(id=inst.id, name=inst.name, code=inst.code, status=inst.status)


# --- Institution profile: Super Admin management ---
@router.get("/admin/institutions", response_model=list[InstitutionProfileOut])
async def list_institutions(
    _: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> list[InstitutionProfileOut]:
    rows = await admin_service.list_institutions(session)
    return [InstitutionProfileOut.of(r) for r in rows]


@router.post("/admin/institutions", status_code=201)
async def create_institution(
    payload: InstitutionCreate,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Super Admin creates an institution with its full profile + first admin."""
    try:
        institution, temp_password = await admin_service.create_institution(
            session, actor_id=current.id, data=payload
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    result: dict = {
        "institution": InstitutionProfileOut.of(institution).model_dump(mode="json"),
        "admin_email": payload.admin_email,
    }
    if not _settings.is_production and temp_password:
        result["debug_admin_temp_password"] = temp_password
    return result


@router.put("/admin/institutions/{institution_id}", response_model=InstitutionProfileOut)
async def update_institution(
    institution_id: int,
    payload: InstitutionProfileIn,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> InstitutionProfileOut:
    try:
        inst = await admin_service.update_institution(
            session, institution_id=institution_id, actor_id=current.id, data=payload
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return InstitutionProfileOut.of(inst)


# --- Institution profile: member view (admin / teacher / student) ---
@router.get("/institutions/{institution_id}/profile", response_model=InstitutionProfileOut)
async def get_institution_profile(
    institution_id: int,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InstitutionProfileOut:
    enforce_tenant_scope(current, institution_id)
    try:
        inst = await admin_service.get_institution(session, institution_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return InstitutionProfileOut.of(inst)


@router.get("/institutions/{institution_id}/logo")
async def get_institution_logo(
    institution_id: int,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    enforce_tenant_scope(current, institution_id)
    try:
        inst = await admin_service.get_institution(session, institution_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    if inst.logo_data is None:
        raise HTTPException(status_code=404, detail="No logo")
    return Response(
        content=inst.logo_data,
        media_type=inst.logo_content_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )


@router.put("/institutions/{institution_id}/logo", response_model=InstitutionProfileOut)
async def upload_institution_logo(
    institution_id: int,
    file: UploadFile = File(...),
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
) -> InstitutionProfileOut:
    # Read at most one byte past the limit so oversized uploads are rejected
    # without buffering the whole file.
    content = await file.read(admin_service.LOGO_MAX_BYTES + 1)
    try:
        inst = await admin_service.set_logo(
            session,
            institution_id=institution_id,
            actor_id=current.id,
            content_type=file.content_type or "",
            content=content,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return InstitutionProfileOut.of(inst)


@router.delete("/institutions/{institution_id}/logo", status_code=204)
async def delete_institution_logo(
    institution_id: int,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
) -> Response:
    try:
        await admin_service.clear_logo(
            session, institution_id=institution_id, actor_id=current.id
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return Response(status_code=204)
