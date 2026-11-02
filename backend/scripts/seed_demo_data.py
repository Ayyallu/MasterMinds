"""Create deterministic synthetic institution data for a local demo only.

Set DEMO_ADMIN_PASSWORD, DEMO_TEACHER_PASSWORD and DEMO_STUDENT_PASSWORD
before running: python -m scripts.seed_demo_data
This script refuses to run when ENVIRONMENT=production.
"""
from __future__ import annotations

import asyncio
import os

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    ClassGroup,
    Institution,
    InstitutionMembership,
    InstitutionStatus,
    Question,
    QuestionOption,
    QuestionStatus,
    QuestionVersion,
    Role,
    RoleName,
    TeacherAssignment,
    User,
    UserRole,
    UserStatus,
)
from app.security import hash_password


INSTITUTION_CODE = "DEMO01"
ACCOUNTS = [
    ("admin@demo.masterminds.local", "Demo Institution Admin", "institution_admin", "DEMO-ADMIN"),
    ("teacher@demo.masterminds.local", "Demo Faculty", "teacher", "DEMO-TEACHER"),
    ("student@demo.masterminds.local", "Demo Student", "student", "MM-DEMO-001"),
]


async def get_or_create_user(session, email: str, name: str, role_name: str, password: str, institution_id: int, register_number: str):
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            email=email,
            full_name=name,
            hashed_password=hash_password(password),
            status=UserStatus.active.value,
            is_super_admin=False,
        )
        session.add(user)
        await session.flush()

    role = await session.scalar(select(Role).where(Role.name == role_name))
    if role is None:
        raise RuntimeError(f"Missing role {role_name}; run Alembic migrations first.")
    role_link = await session.scalar(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.role_id == role.id,
            UserRole.institution_id == institution_id,
        )
    )
    if role_link is None:
        session.add(UserRole(user_id=user.id, role_id=role.id, institution_id=institution_id))

    membership = await session.scalar(
        select(InstitutionMembership).where(
            InstitutionMembership.user_id == user.id,
            InstitutionMembership.institution_id == institution_id,
        )
    )
    if membership is None:
        session.add(
            InstitutionMembership(
                user_id=user.id,
                institution_id=institution_id,
                register_number=register_number,
                status=UserStatus.active.value,
            )
        )
    return user


async def seed() -> None:
    settings = get_settings()
    if settings.is_production:
        raise SystemExit("Refusing to seed demo accounts in production.")

    passwords = [
        os.getenv("DEMO_ADMIN_PASSWORD", ""),
        os.getenv("DEMO_TEACHER_PASSWORD", ""),
        os.getenv("DEMO_STUDENT_PASSWORD", ""),
    ]
    if any(len(password) < 12 for password in passwords):
        raise SystemExit(
            "Set DEMO_ADMIN_PASSWORD, DEMO_TEACHER_PASSWORD and "
            "DEMO_STUDENT_PASSWORD to values of at least 12 characters."
        )

    async with SessionLocal() as session:
        institution = await session.scalar(
            select(Institution).where(Institution.code == INSTITUTION_CODE)
        )
        if institution is None:
            institution = Institution(
                name="MasterMinds Demo Academy",
                code=INSTITUTION_CODE,
                status=InstitutionStatus.active.value,
            )
            session.add(institution)
            await session.flush()

        users = []
        for account, password in zip(ACCOUNTS, passwords):
            users.append(
                await get_or_create_user(
                    session,
                    account[0],
                    account[1],
                    account[2],
                    password,
                    institution.id,
                    account[3],
                )
            )
        admin, teacher, student = users

        group = await session.scalar(
            select(ClassGroup).where(
                ClassGroup.institution_id == institution.id,
                ClassGroup.name == "Grade 10 - Section A",
            )
        )
        if group is None:
            group = ClassGroup(
                institution_id=institution.id,
                name="Grade 10 - Section A",
                kind="class",
            )
            session.add(group)
            await session.flush()

        assignment = await session.scalar(
            select(TeacherAssignment).where(
                TeacherAssignment.teacher_user_id == teacher.id,
                TeacherAssignment.class_group_id == group.id,
            )
        )
        if assignment is None:
            session.add(
                TeacherAssignment(
                    institution_id=institution.id,
                    teacher_user_id=teacher.id,
                    class_group_id=group.id,
                )
            )

        question_count = await session.scalar(
            select(Question.id).where(
                Question.institution_id == institution.id,
                Question.withdrawn.is_(False),
            ).limit(1)
        )
        if question_count is None:
            samples = [
                ("Which gas do plants absorb during photosynthesis?", ["Oxygen", "Carbon dioxide", "Nitrogen", "Hydrogen"], 1),
                ("What is the SI unit of force?", ["Joule", "Watt", "Newton", "Pascal"], 2),
                ("Which part of the cell contains genetic material?", ["Nucleus", "Ribosome", "Cell wall", "Vacuole"], 0),
                ("What is 12 × 8?", ["86", "92", "96", "108"], 2),
                ("Which planet is known as the Red Planet?", ["Venus", "Mars", "Jupiter", "Mercury"], 1),
            ]
            for prompt, options, correct in samples:
                question = Question(
                    institution_id=institution.id,
                    is_global=False,
                    created_by_user_id=teacher.id,
                )
                session.add(question)
                await session.flush()
                version = QuestionVersion(
                    question_id=question.id,
                    version_no=1,
                    type="single_mcq",
                    text=prompt,
                    difficulty="easy",
                    marks=1,
                    status=QuestionStatus.approved.value,
                    created_by_user_id=teacher.id,
                    approved_by_user_id=admin.id,
                )
                session.add(version)
                await session.flush()
                session.add_all(
                    [
                        QuestionOption(
                            question_version_id=version.id,
                            text=option,
                            is_correct=index == correct,
                            order_index=index,
                        )
                        for index, option in enumerate(options)
                    ]
                )

        await session.commit()

    print("Synthetic demo data is ready.")
    print(f"Institution: {INSTITUTION_CODE} (MasterMinds Demo Academy)")
    print(f"Admin:   {ACCOUNTS[0][0]}")
    print(f"Faculty: {ACCOUNTS[1][0]}")
    print(f"Student: {ACCOUNTS[2][0]} / register number {ACCOUNTS[2][3]}")
    print("Passwords are the values supplied in the three DEMO_*_PASSWORD variables.")


if __name__ == "__main__":
    asyncio.run(seed())
