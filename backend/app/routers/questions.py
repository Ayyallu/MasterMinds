"""Phase 4 endpoints: syllabus, question bank, private document uploads."""
from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.dependencies import require_institution_admin, require_institution_staff
from app.models import LearningObjective, SyllabusTopic
from app.schemas import CurrentUser
from app.schemas_questions import (
    ObjectiveCreate,
    QuestionCreate,
    QuestionSearch,
    TopicCreate,
)
from app.services import document_service, question_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/institutions/{institution_id}", tags=["questions"])


def _err(exc: AuthError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


# --- Syllabus structure ---
@router.post("/topics", status_code=201)
async def add_topic(
    institution_id: int,
    payload: TopicCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    topic = SyllabusTopic(
        institution_id=institution_id,
        name=payload.name,
        course_id=payload.course_id,
        grade_level_id=payload.grade_level_id,
        term_id=payload.term_id,
        parent_id=payload.parent_id,
    )
    session.add(topic)
    await session.commit()
    return {"id": topic.id}


@router.post("/objectives", status_code=201)
async def add_objective(
    institution_id: int,
    payload: ObjectiveCreate,
    _: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    topic = await session.get(SyllabusTopic, payload.topic_id)
    if topic is None or topic.institution_id != institution_id:
        raise HTTPException(status_code=404, detail="Topic not in this institution")
    obj = LearningObjective(
        institution_id=institution_id,
        topic_id=payload.topic_id,
        code=payload.code,
        description=payload.description,
    )
    session.add(obj)
    await session.commit()
    return {"id": obj.id}


# --- Question bank ---
@router.post("/questions", status_code=201)
async def create_question(
    institution_id: int,
    payload: QuestionCreate,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    v = await question_service.create_question(
        session, institution_id, current.id, payload
    )
    await session.commit()
    return {"question_id": v.question_id, "version_id": v.id, "status": v.status}


@router.post("/questions/{question_id}/versions", status_code=201)
async def add_version(
    institution_id: int,
    question_id: int,
    payload: QuestionCreate,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    try:
        v = await question_service.add_version(
            session, institution_id, question_id, current.id, payload
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"version_id": v.id, "version_no": v.version_no, "status": v.status}


@router.post("/versions/{version_id}/submit")
async def submit_version(
    institution_id: int,
    version_id: int,
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    try:
        v = await question_service.submit_for_review(
            session, institution_id, version_id, current.id
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"version_id": v.id, "status": v.status}


@router.post("/versions/{version_id}/review")
async def review_version(
    institution_id: int,
    version_id: int,
    approve: bool,
    current: CurrentUser = Depends(require_institution_admin()),
    session: AsyncSession = Depends(get_session),
):
    try:
        v = await question_service.review_version(
            session, institution_id, version_id, current.id, approve
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"version_id": v.id, "status": v.status}


@router.get("/questions/{question_id}/versions")
async def list_versions(
    institution_id: int,
    question_id: int,
    _: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    try:
        versions = await question_service.list_versions(
            session, institution_id, question_id
        )
    except AuthError as exc:
        raise _err(exc)
    out = []
    for v in versions:
        opts = await question_service.load_options(session, v.id)
        out.append(question_service.serialize(v, opts, include_keys=True))
    return out


@router.post("/questions/search")
async def search_questions(
    institution_id: int,
    filters: QuestionSearch,
    _: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    versions = await question_service.search(session, institution_id, filters)
    out = []
    for v in versions:
        opts = await question_service.load_options(session, v.id)
        out.append(question_service.serialize(v, opts, include_keys=True))
    return out


# --- Private documents ---
@router.post("/documents", status_code=201)
async def upload_document(
    institution_id: int,
    file: UploadFile = File(...),
    current: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    content = await file.read()
    try:
        doc = await document_service.store_document(
            session,
            institution_id=institution_id,
            actor_id=current.id,
            filename=file.filename or "upload",
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )
    except AuthError as exc:
        raise _err(exc)
    await session.commit()
    return {"id": doc.id, "filename": doc.filename, "size_bytes": doc.size_bytes}


@router.get("/documents/{document_id}/download")
async def download_document(
    institution_id: int,
    document_id: int,
    _: CurrentUser = Depends(require_institution_staff()),
    session: AsyncSession = Depends(get_session),
):
    try:
        doc = await document_service.get_document(session, institution_id, document_id)
    except AuthError as exc:
        raise _err(exc)
    return FileResponse(
        doc.storage_path, media_type=doc.content_type, filename=doc.filename
    )
