"""Shared helpers for creating users, granting roles and memberships."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    InstitutionMembership,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
)
from app.security import hash_password


async def get_role_id(session: AsyncSession, role: RoleName) -> int:
    res = await session.execute(select(Role.id).where(Role.name == role.value))
    role_id = res.scalar_one_or_none()
    if role_id is None:
        raise ValueError(f"Role {role.value} is not seeded")
    return role_id


async def grant_role(
    session: AsyncSession,
    user_id: int,
    role: RoleName,
    institution_id: int | None,
) -> None:
    role_id = await get_role_id(session, role)
    exists = await session.execute(
        select(UserRole.id).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.institution_id.is_(institution_id)
            if institution_id is None
            else UserRole.institution_id == institution_id,
        )
    )
    if exists.scalar_one_or_none() is None:
        session.add(
            UserRole(user_id=user_id, role_id=role_id, institution_id=institution_id)
        )


async def ensure_membership(
    session: AsyncSession,
    user_id: int,
    institution_id: int,
    *,
    register_number: str | None = None,
    status: str = UserStatus.active.value,
) -> InstitutionMembership:
    res = await session.execute(
        select(InstitutionMembership).where(
            InstitutionMembership.user_id == user_id,
            InstitutionMembership.institution_id == institution_id,
        )
    )
    membership = res.scalar_one_or_none()
    if membership is None:
        membership = InstitutionMembership(
            user_id=user_id,
            institution_id=institution_id,
            register_number=register_number,
            status=status,
        )
        session.add(membership)
    return membership


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    res = await session.execute(select(User).where(User.email == email.lower()))
    return res.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    email: str | None,
    full_name: str,
    password: str,
    status: str = UserStatus.active.value,
    is_super_admin: bool = False,
) -> User:
    user = User(
        email=email.lower() if email else None,
        full_name=full_name,
        hashed_password=hash_password(password),
        status=status,
        is_super_admin=is_super_admin,
    )
    session.add(user)
    await session.flush()
    return user
