"""FastAPI dependencies: bearer auth, role policies, tenant-scope enforcement."""
from __future__ import annotations

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import RoleName, User, UserStatus
from app.schemas import CurrentUser
from app.security import decode_access_token
from app.services import auth_service


async def get_current_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    user_id = int(payload["sub"])
    user = await session.get(User, user_id)
    if user is None or user.status != UserStatus.active.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not active"
        )

    roles = await auth_service.get_user_roles(session, user_id)
    institution_ids = await auth_service.get_user_institution_ids(session, user_id)
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_super_admin=user.is_super_admin,
        roles=roles,
        institution_ids=institution_ids,
    )


def require_roles(*required: RoleName):
    """Dependency factory: allow the request only if the user holds a role."""
    allowed = {r.value for r in required}

    async def _dep(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.is_super_admin or allowed.intersection(current.roles):
            return current
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role"
        )

    return _dep


def require_super_admin():
    async def _dep(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Super Admin required",
            )
        return current

    return _dep


def require_institution_admin():
    """Path dependency: caller must be Super Admin, or an Institution Admin
    scoped to the {institution_id} in the route."""

    async def _dep(
        institution_id: int, current: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if current.is_super_admin:
            return current
        if RoleName.institution_admin.value not in current.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Institution Admin required",
            )
        enforce_tenant_scope(current, institution_id)
        return current

    return _dep


def enforce_tenant_scope(current: CurrentUser, institution_id: int) -> None:
    """Server-side tenant guard. Never trust a browser-supplied institution id.

    Super Admin may cross tenants (an explicit privileged path); everyone else
    is restricted to their own institution memberships.
    """
    if current.is_super_admin:
        return
    if institution_id not in current.institution_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Outside your institution scope",
        )
