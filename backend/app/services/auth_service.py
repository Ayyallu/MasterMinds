"""Authentication, session rotation, tenant-aware identity services."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AuditEvent,
    Institution,
    InstitutionMembership,
    InstitutionStatus,
    PasswordResetToken,
    RefreshToken,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
)
from app.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
    verify_totp,
)

_settings = get_settings()


class AuthError(Exception):
    """Raised for authentication/authorization failures (maps to 401/403)."""

    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    """Treat naive timestamps (e.g. from SQLite) as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def record_audit(
    session: AsyncSession,
    event_type: str,
    *,
    actor_user_id: int | None = None,
    institution_id: int | None = None,
    target: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
) -> None:
    session.add(
        AuditEvent(
            event_type=event_type,
            actor_user_id=actor_user_id,
            institution_id=institution_id,
            target=target,
            detail=detail,
            ip=ip,
        )
    )


async def get_user_roles(session: AsyncSession, user_id: int) -> list[str]:
    rows = await session.execute(
        select(Role.name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    )
    return sorted({r for (r,) in rows.all()})


async def get_user_institution_ids(session: AsyncSession, user_id: int) -> list[int]:
    """Institutions the user may act in: active membership AND active institution.
    A disabled institution drops out here, so tenant-scope checks deny it."""
    rows = await session.execute(
        select(InstitutionMembership.institution_id)
        .join(Institution, Institution.id == InstitutionMembership.institution_id)
        .where(
            InstitutionMembership.user_id == user_id,
            InstitutionMembership.status == UserStatus.active.value,
            Institution.status == InstitutionStatus.active.value,
        )
    )
    return sorted({i for (i,) in rows.all()})


async def institution_access_blocked(session: AsyncSession, user: User) -> bool:
    """True when a (non-platform) user's only institutions are disabled."""
    if user.is_super_admin:
        return False
    has_membership = await session.scalar(
        select(InstitutionMembership.id).where(
            InstitutionMembership.user_id == user.id,
            InstitutionMembership.status == UserStatus.active.value,
        ).limit(1)
    )
    if has_membership is None:
        return False  # platform-only users (e.g. central reviewer)
    return not await get_user_institution_ids(session, user.id)


async def _find_user_for_login(
    session: AsyncSession,
    *,
    email: str | None,
    institution_code: str | None,
    register_number: str | None,
) -> User | None:
    if email is not None:
        res = await session.execute(select(User).where(User.email == email.lower()))
        return res.scalar_one_or_none()

    # Register-number login is scoped to a single institution.
    inst_res = await session.execute(
        select(Institution).where(Institution.code == institution_code)
    )
    institution = inst_res.scalar_one_or_none()
    if institution is None:
        return None
    mem_res = await session.execute(
        select(InstitutionMembership).where(
            InstitutionMembership.institution_id == institution.id,
            InstitutionMembership.register_number == register_number,
        )
    )
    membership = mem_res.scalar_one_or_none()
    if membership is None:
        return None
    user_res = await session.execute(select(User).where(User.id == membership.user_id))
    return user_res.scalar_one_or_none()


async def authenticate(
    session: AsyncSession,
    *,
    email: str | None,
    institution_code: str | None,
    register_number: str | None,
    password: str,
    totp_code: str | None,
) -> User:
    user = await _find_user_for_login(
        session,
        email=email,
        institution_code=institution_code,
        register_number=register_number,
    )
    # Always verify against something to reduce user-enumeration timing signals.
    if user is None:
        verify_password(password, hash_password("placeholder"))
        raise AuthError("Invalid credentials")

    if not verify_password(password, user.hashed_password):
        raise AuthError("Invalid credentials")

    if user.status == UserStatus.disabled.value:
        raise AuthError("Account is disabled", status_code=403)
    if user.status != UserStatus.active.value:
        raise AuthError("Account is not active", status_code=403)

    if await institution_access_blocked(session, user):
        raise AuthError("Your institution's access has been disabled", status_code=403)

    if user.mfa_enabled:
        if not totp_code:
            raise AuthError("MFA code required", status_code=401)
        if not verify_totp(user.totp_secret or "", totp_code):
            raise AuthError("Invalid MFA code", status_code=401)

    return user


async def issue_tokens(
    session: AsyncSession, user: User, *, family_id: str | None = None
) -> tuple[str, str]:
    roles = await get_user_roles(session, user.id)
    institution_ids = await get_user_institution_ids(session, user.id)
    access = create_access_token(
        user.id,
        claims={
            "roles": roles,
            "institution_ids": institution_ids,
            "is_super_admin": user.is_super_admin,
        },
    )

    raw_refresh = generate_opaque_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            family_id=family_id or uuid.uuid4().hex,
            expires_at=_utcnow() + timedelta(days=_settings.refresh_token_ttl_days),
        )
    )
    return access, raw_refresh


async def _revoke_family(session: AsyncSession, family_id: str) -> None:
    rows = await session.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
        )
    )
    for token in rows.scalars().all():
        token.revoked_at = _utcnow()


async def rotate_refresh(
    session: AsyncSession, raw_refresh: str
) -> tuple[str, str]:
    res = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
    )
    token = res.scalar_one_or_none()
    if token is None:
        raise AuthError("Invalid refresh token")

    # Replay detection: a token presented after it was already rotated or
    # revoked means the whole family is compromised.
    if token.revoked_at is not None or token.used_at is not None:
        await _revoke_family(session, token.family_id)
        await record_audit(
            session,
            "refresh_token.replay_detected",
            actor_user_id=token.user_id,
            detail={"family_id": token.family_id},
        )
        raise AuthError("Refresh token reuse detected; session revoked")

    if _aware(token.expires_at) < _utcnow():
        raise AuthError("Refresh token expired")

    user_res = await session.execute(select(User).where(User.id == token.user_id))
    user = user_res.scalar_one_or_none()
    if user is None or user.status != UserStatus.active.value:
        raise AuthError("Account is not active", status_code=403)
    if await institution_access_blocked(session, user):
        raise AuthError("Your institution's access has been disabled", status_code=403)

    token.used_at = _utcnow()
    return await issue_tokens(session, user, family_id=token.family_id)


async def revoke_refresh(
    session: AsyncSession, raw_refresh: str, *, all_sessions: bool
) -> None:
    res = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))
    )
    token = res.scalar_one_or_none()
    if token is None:
        return
    if all_sessions:
        rows = await session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == token.user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        for t in rows.scalars().all():
            t.revoked_at = _utcnow()
    else:
        token.revoked_at = _utcnow()


# --- Password management ---
async def create_password_reset(session: AsyncSession, email: str) -> str | None:
    res = await session.execute(select(User).where(User.email == email.lower()))
    user = res.scalar_one_or_none()
    if user is None:
        return None  # Do not reveal whether the email exists.
    raw = generate_opaque_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            expires_at=_utcnow()
            + timedelta(minutes=_settings.password_reset_ttl_minutes),
        )
    )
    return raw


async def confirm_password_reset(
    session: AsyncSession, raw_token: str, new_password: str
) -> None:
    res = await session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_token(raw_token)
        )
    )
    token = res.scalar_one_or_none()
    if token is None or token.used_at is not None:
        raise AuthError("Invalid or used reset token")
    if _aware(token.expires_at) < _utcnow():
        raise AuthError("Reset token expired")

    user_res = await session.execute(select(User).where(User.id == token.user_id))
    user = user_res.scalar_one()
    user.hashed_password = hash_password(new_password)
    token.used_at = _utcnow()
    await _revoke_all_user_tokens(session, user.id)


async def change_password(
    session: AsyncSession, user: User, current: str, new_password: str
) -> None:
    if not verify_password(current, user.hashed_password):
        raise AuthError("Current password is incorrect", status_code=400)
    user.hashed_password = hash_password(new_password)
    await _revoke_all_user_tokens(session, user.id)


async def _revoke_all_user_tokens(session: AsyncSession, user_id: int) -> None:
    rows = await session.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    for t in rows.scalars().all():
        t.revoked_at = _utcnow()
