"""Create the first platform Super Admin for a freshly migrated database.

Run from backend/: python -m scripts.create_super_admin
The password is read interactively and is never printed or stored in plaintext.
"""
from __future__ import annotations

import asyncio
from getpass import getpass

from sqlalchemy import select
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.db import SessionLocal
from app.models import Role, RoleName, User, UserRole, UserStatus
from app.security import hash_password


async def create_super_admin(email: str, full_name: str, password: str) -> None:
    normalized_email = email.strip().lower()
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(User).where(User.email == normalized_email)
        )
        if existing is not None:
            if not existing.is_super_admin or existing.status != UserStatus.active.value:
                raise SystemExit(
                    "That email already belongs to a non-active/non-super-admin account. "
                    "Use a different email; this script will not elevate existing users."
                )
            user = existing
            print(f"Active Super Admin already exists: {normalized_email}")
        else:
            user = User(
                email=normalized_email,
                full_name=full_name.strip(),
                hashed_password=hash_password(password),
                status=UserStatus.active.value,
                is_super_admin=True,
                mfa_enabled=False,
            )
            session.add(user)
            await session.flush()

        role = await session.scalar(
            select(Role).where(Role.name == RoleName.super_admin.value)
        )
        if role is None:
            raise SystemExit("Role seed is missing. Run: alembic upgrade head")
        assignment = await session.scalar(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
                UserRole.institution_id.is_(None),
            )
        )
        if assignment is None:
            session.add(
                UserRole(user_id=user.id, role_id=role.id, institution_id=None)
            )
        await session.commit()
        print(f"Super Admin ready: {normalized_email}")


def main() -> None:
    email = input("Super Admin email (e.g. superadmin@demo.example.com): ").strip()
    try:
        email = str(TypeAdapter(EmailStr).validate_python(email))
    except ValidationError as exc:
        raise SystemExit("Enter a valid sign-in email address (avoid reserved TLDs such as .local).") from exc
    full_name = input("Full name: ").strip()
    password = getpass("Password (minimum 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if not email or not full_name:
        raise SystemExit("Email and full name are required.")
    if len(password) < 12:
        raise SystemExit("Use a password with at least 12 characters.")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    asyncio.run(create_super_admin(email, full_name, password))


if __name__ == "__main__":
    main()
