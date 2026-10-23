"""Tenant-scoped CSV roster import: validate, preview, idempotent commit."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from pydantic import ValidationError
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ClassGroup,
    Enrollment,
    EnrollmentStatus,
    ImportStatus,
    InstitutionMembership,
    RoleName,
    RosterImport,
    UserStatus,
)
from app.security import generate_opaque_token
from app.services import provisioning
from app.services.auth_service import record_audit

REQUIRED_COLUMNS = {"register_number", "full_name"}
MAX_ROWS = 5000


class _Row(BaseModel):
    email: EmailStr | None = None


def _valid_email(value: str) -> bool:
    try:
        _Row(email=value)
        return True
    except ValidationError:
        return False


async def process_roster(
    session: AsyncSession,
    *,
    institution_id: int,
    actor_id: int,
    csv_text: str,
    class_group_code: str | None,
    commit: bool,
) -> RosterImport:
    reader = csv.DictReader(io.StringIO(csv_text))
    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    errors: list[dict] = []

    record = RosterImport(
        institution_id=institution_id,
        created_by_user_id=actor_id,
        status=ImportStatus.validated.value,
        total_rows=0,
        valid_rows=0,
        error_rows=0,
    )

    if not REQUIRED_COLUMNS.issubset(headers):
        missing = ", ".join(sorted(REQUIRED_COLUMNS - headers))
        record.status = ImportStatus.failed.value
        record.errors = [{"row": 0, "message": f"Missing columns: {missing}"}]
        record.error_rows = 1
        record.finished_at = datetime.now(timezone.utc)
        session.add(record)
        await session.flush()
        return record

    # Resolve optional target class group (tenant-scoped).
    class_group: ClassGroup | None = None
    if class_group_code:
        res = await session.execute(
            select(ClassGroup).where(
                ClassGroup.institution_id == institution_id,
                ClassGroup.name == class_group_code,
            )
        )
        class_group = res.scalar_one_or_none()
        if class_group is None:
            record.status = ImportStatus.failed.value
            record.errors = [
                {"row": 0, "message": f"Unknown class group: {class_group_code}"}
            ]
            record.error_rows = 1
            record.finished_at = datetime.now(timezone.utc)
            session.add(record)
            await session.flush()
            return record

    seen_in_file: set[str] = set()
    valid_rows: list[dict] = []

    for idx, raw in enumerate(reader, start=1):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        register = row.get("register_number", "")
        full_name = row.get("full_name", "")
        email = row.get("email") or None

        if not register or not full_name:
            errors.append({"row": idx, "message": "register_number and full_name required"})
            continue
        if register in seen_in_file:
            errors.append({"row": idx, "message": f"Duplicate register_number in file: {register}"})
            continue
        if email and not _valid_email(email):
            errors.append({"row": idx, "message": f"Invalid email: {email}"})
            continue
        seen_in_file.add(register)
        valid_rows.append({"register_number": register, "full_name": full_name, "email": email})

    record.total_rows = len(valid_rows) + len(errors)
    record.valid_rows = len(valid_rows)
    record.error_rows = len(errors)
    record.errors = errors or None

    if commit and not errors:
        # Idempotent: skip register numbers that already exist in the institution.
        existing_res = await session.execute(
            select(InstitutionMembership.register_number).where(
                InstitutionMembership.institution_id == institution_id,
                InstitutionMembership.register_number.is_not(None),
            )
        )
        existing = {r for (r,) in existing_res.all()}
        for item in valid_rows:
            if item["register_number"] in existing:
                continue  # safe retry
            # Imported students get a random password; they set their own via
            # the password-reset flow. No real credential is ever logged.
            user = await provisioning.create_user(
                session,
                email=item["email"],
                full_name=item["full_name"],
                password=generate_opaque_token(),
                status=UserStatus.active.value,
            )
            await provisioning.grant_role(
                session, user.id, RoleName.student, institution_id
            )
            await provisioning.ensure_membership(
                session,
                user.id,
                institution_id,
                register_number=item["register_number"],
                status=UserStatus.active.value,
            )
            if class_group is not None:
                session.add(
                    Enrollment(
                        institution_id=institution_id,
                        student_user_id=user.id,
                        class_group_id=class_group.id,
                        status=EnrollmentStatus.active.value,
                    )
                )
        record.status = ImportStatus.committed.value
        record.finished_at = datetime.now(timezone.utc)
        await record_audit(
            session,
            "roster.imported",
            actor_user_id=actor_id,
            institution_id=institution_id,
            detail={"valid": record.valid_rows, "errors": record.error_rows},
        )
    elif commit and errors:
        record.status = ImportStatus.failed.value

    session.add(record)
    await session.flush()
    return record
