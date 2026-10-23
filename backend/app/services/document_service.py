"""Private document storage. Files live outside the DB and are never executed."""
from __future__ import annotations

import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Document
from app.services.auth_service import AuthError, record_audit

_settings = get_settings()


def _safe_name(filename: str) -> str:
    base = os.path.basename(filename or "upload")
    # Strip any path separators / nulls; keep it simple and inert.
    return base.replace("\\", "_").replace("/", "_").replace("\x00", "")[:200] or "upload"


async def store_document(
    session: AsyncSession,
    *,
    institution_id: int,
    actor_id: int,
    filename: str,
    content_type: str,
    content: bytes,
) -> Document:
    if content_type not in _settings.upload_allowed_types:
        raise AuthError(f"Unsupported file type: {content_type}", 400)
    if len(content) == 0:
        raise AuthError("Empty file", 400)
    if len(content) > _settings.upload_max_bytes:
        raise AuthError("File exceeds maximum allowed size", 400)

    safe = _safe_name(filename)
    inst_dir = os.path.join(_settings.uploads_dir, str(institution_id))
    os.makedirs(inst_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{safe}"
    path = os.path.join(inst_dir, stored_name)
    with open(path, "wb") as fh:
        fh.write(content)

    doc = Document(
        institution_id=institution_id,
        uploaded_by_user_id=actor_id,
        filename=safe,
        content_type=content_type,
        size_bytes=len(content),
        storage_path=path,
    )
    session.add(doc)
    await record_audit(
        session,
        "document.uploaded",
        actor_user_id=actor_id,
        institution_id=institution_id,
        target=safe,
    )
    await session.flush()
    return doc


async def get_document(
    session: AsyncSession, institution_id: int, document_id: int
) -> Document:
    doc = await session.get(Document, document_id)
    if doc is None or doc.institution_id != institution_id:
        raise AuthError("Document not found", 404)
    return doc
