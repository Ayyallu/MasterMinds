"""Authentication, session and tenant-security endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import rate_limit
from app.db import get_session
from app.dependencies import enforce_tenant_scope, get_current_user, require_super_admin
from app.models import User
from app.schemas import (
    CurrentUser,
    LoginRequest,
    LogoutRequest,
    MFAEnableRequest,
    MFASetupResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    TokenResponse,
)
from app.security import (
    generate_totp_secret,
    hash_password,
    totp_provisioning_uri,
    verify_totp,
)
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    ip = _client_ip(request)
    identifier = payload.email or f"{payload.institution_code}:{payload.register_number}"
    rl_key = f"{identifier}|{ip}"

    if rate_limit.is_rate_limited(rl_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts; try again later.",
        )

    try:
        user = await auth_service.authenticate(
            session,
            email=payload.email,
            institution_code=payload.institution_code,
            register_number=payload.register_number,
            password=payload.password,
            totp_code=payload.totp_code,
        )
    except AuthError as exc:
        rate_limit.record_attempt(rl_key)
        await auth_service.record_audit(
            session, "auth.login_failed", target=identifier, ip=ip
        )
        await session.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    rate_limit.reset(rl_key)
    access, refresh = await auth_service.issue_tokens(session, user)
    await auth_service.record_audit(
        session, "auth.login_success", actor_user_id=user.id, ip=ip
    )
    await session.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, session: AsyncSession = Depends(get_session)
) -> TokenResponse:
    try:
        access, new_refresh = await auth_service.rotate_refresh(
            session, payload.refresh_token
        )
    except AuthError as exc:
        await session.commit()  # persist replay-revocation / audit
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(
    payload: LogoutRequest, session: AsyncSession = Depends(get_session)
) -> Response:
    await auth_service.revoke_refresh(
        session, payload.refresh_token, all_sessions=payload.all_sessions
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUser)
async def me(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return current


@router.post("/password/reset-request", status_code=status.HTTP_202_ACCEPTED)
async def reset_request(
    payload: PasswordResetRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    raw = await auth_service.create_password_reset(session, payload.email)
    await auth_service.record_audit(
        session, "auth.password_reset_requested", target=payload.email
    )
    await session.commit()
    # Email delivery is stubbed; in dev we return the token so the flow is
    # testable without an email provider. Never do this in production.
    response: dict = {"status": "accepted"}
    settings = auth_service._settings
    if not settings.is_production and raw is not None:
        response["debug_reset_token"] = raw
    return response


@router.post(
    "/password/reset-confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def reset_confirm(
    payload: PasswordResetConfirm, session: AsyncSession = Depends(get_session)
) -> Response:
    try:
        await auth_service.confirm_password_reset(
            session, payload.token, payload.new_password
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/password/change",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def change_password(
    payload: PasswordChangeRequest,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await session.get(User, current.id)
    try:
        await auth_service.change_password(
            session, user, payload.current_password, payload.new_password
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    await auth_service.record_audit(
        session, "auth.password_changed", actor_user_id=current.id
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- MFA (TOTP) for Super Admin ---
@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> MFASetupResponse:
    user = await session.get(User, current.id)
    secret = generate_totp_secret()
    user.totp_secret = secret  # staged; not active until enable confirms a code
    await session.commit()
    account = user.email or f"user:{user.id}"
    return MFASetupResponse(
        secret=secret, otpauth_uri=totp_provisioning_uri(secret, account)
    )


@router.post(
    "/mfa/enable", status_code=status.HTTP_204_NO_CONTENT, response_class=Response
)
async def mfa_enable(
    payload: MFAEnableRequest,
    current: CurrentUser = Depends(require_super_admin()),
    session: AsyncSession = Depends(get_session),
) -> Response:
    user = await session.get(User, current.id)
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="Run /auth/mfa/setup first")
    if not verify_totp(user.totp_secret, payload.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    user.mfa_enabled = True
    await auth_service.record_audit(
        session, "auth.mfa_enabled", actor_user_id=current.id
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Tenant-scope demonstration (proves server-side isolation) ---
@router.get("/tenant/{institution_id}/context")
async def tenant_context(
    institution_id: int,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return tenant-scoped context. Access is enforced server-side; a
    manipulated institution_id cannot reach another tenant's data."""
    enforce_tenant_scope(current, institution_id)
    if current.is_super_admin and institution_id not in current.institution_ids:
        # Explicit privileged cross-tenant access -> audit event.
        await auth_service.record_audit(
            session,
            "tenant.cross_tenant_access",
            actor_user_id=current.id,
            institution_id=institution_id,
            ip=_client_ip(request),
        )
        await session.commit()
    return {"institution_id": institution_id, "actor": current.id}
