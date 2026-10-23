from __future__ import annotations

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app import main, rate_limit
from app.db import Base, get_session
from app.models import (
    Institution,
    InstitutionMembership,
    InstitutionStatus,
    Role,
    RoleName,
    User,
    UserRole,
    UserStatus,
)
from app.security import hash_password

ROLE_NAMES = [r.value for r in RoleName]


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed roles.
    sm = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with sm() as s:
        for name in ROLE_NAMES:
            s.add(Role(name=name))
        await s.commit()
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def sessionmaker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(sessionmaker):
    async def _override_get_session():
        async with sessionmaker() as s:
            yield s

    main.app.dependency_overrides[get_session] = _override_get_session
    rate_limit.clear_all()
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    main.app.dependency_overrides.clear()


# --- Factory helpers ---
@pytest_asyncio.fixture
async def factory(sessionmaker):
    async def _make_institution(code: str, name: str | None = None) -> Institution:
        async with sessionmaker() as s:
            inst = Institution(
                name=name or code,
                code=code,
                status=InstitutionStatus.active.value,
            )
            s.add(inst)
            await s.commit()
            await s.refresh(inst)
            return inst

    async def _make_user(
        *,
        email: str | None = None,
        password: str = "Password123!",
        full_name: str = "Test User",
        status: str = UserStatus.active.value,
        is_super_admin: bool = False,
        role: RoleName | None = None,
        institution: Institution | None = None,
        register_number: str | None = None,
    ) -> User:
        async with sessionmaker() as s:
            user = User(
                email=email.lower() if email else None,
                full_name=full_name,
                hashed_password=hash_password(password),
                status=status,
                is_super_admin=is_super_admin,
            )
            s.add(user)
            await s.commit()
            await s.refresh(user)

            if role is not None:
                role_row = (
                    await s.execute(
                        __import__("sqlalchemy").select(Role).where(
                            Role.name == role.value
                        )
                    )
                ).scalar_one()
                s.add(
                    UserRole(
                        user_id=user.id,
                        role_id=role_row.id,
                        institution_id=institution.id if institution else None,
                    )
                )
            if institution is not None:
                s.add(
                    InstitutionMembership(
                        user_id=user.id,
                        institution_id=institution.id,
                        register_number=register_number,
                        status=UserStatus.active.value,
                    )
                )
            await s.commit()
            await s.refresh(user)
            return user

    return type(
        "Factory",
        (),
        {"institution": staticmethod(_make_institution), "user": staticmethod(_make_user)},
    )
