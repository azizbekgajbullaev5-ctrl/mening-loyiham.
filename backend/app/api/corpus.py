from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.core.config import csv_list, get_settings
from app.core.database import get_db
from app.document_processing.validation import ValidationError, validate_upload
from app.models import CorpusJob, CorpusJobItem, RefDocument, User
from app.plagiarism import corpus, jobs
from app.plagiarism.harvest.sources import HARVESTERS
from app.services import storage
from app.services.audit import audit

router = APIRouter(prefix="/corpus", tags=["corpus"])
DOC_KINDS = ("textbook", "article", "dissertation", "autoreferat", "monograph", "study_guide", "other")


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not (user.is_admin or user.email.lower() in get_settings().admin_emails):
        raise HTTPException(403, "admin_only")
    return user


def _ref_out(d: RefDocument) -> dict:
    return {
        "id": d.id, "title": d.title, "authors": d.authors, "year": d.year, "doc_kind": d.doc_kind, "source_type": d.source_type,
        "source_url": d.source_url, "doi": d.doi, "language": d.language, "folder": d.folder, "filename": d.filename,
        "word_count": d.word_count, "fingerprint_count": d.fingerprint_count, "vector_count": d.vector_count,
        "fulltext": d.fulltext, "created_at": d.created_at,
    }


def _job_out(j: CorpusJob) -> dict:
    return {
        "id": j.id, "kind": j.kind, "status": j.status, "params": j.params, "total": j.total, "done": j.done, "added": j.added,
        "skipped": j.skipped, "failed": j.failed, "message": j.message, "log": (j.log or [])[-30:],
        "created_at": j.created_at, "finished_at": j.finished_at,
    }


@router.get("/stats")
def stats(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return corpus.stats(db)


@router.get("/documents")
def list_documents(
    q: str | None = Query(None, max_length=200), kind: str | None = None, source: str | None = None,
    page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
    _: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    stmt = select(RefDocument)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(RefDocument.title.ilike(like), RefDocument.authors.ilike(like), RefDocument.folder.ilike(like), RefDocument.doi.ilike(like)))
    if kind:
        stmt = stmt.where(RefDocument.doc_kind == kind)
    if source:
        stmt = stmt.where(RefDocument.source_type == source)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(RefDocument.created_at.desc()).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": [_ref_out(d) for d in rows]}


@router.delete("/documents/{ref_id}")
def delete_document(ref_id: str, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not corpus.delete_ref(db, ref_id):
        raise HTTPException(404, "not_found")
    audit(db, "corpus_document_deleted", user.id, "ref_document", ref_id, client_ip(request))
    db.commit()
    return {"ok": True}


@router.post("/upload", status_code=201)
async def upload(
    request: Request,
    files: list[UploadFile] = File(...),
    paths: list[str] = Form(default=[]),
    doc_kind: str = Form("other"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Bulk upload (e.g. a whole folder). Files are only indexed; originals are deleted after indexing."""
    s = get_settings()
    if doc_kind not in DOC_KINDS:
        raise HTTPException(422, "invalid_doc_kind")
    if len(files) > 200:
        raise HTTPException(422, "too_many_files")
    job = CorpusJob(kind="ingest", created_by=user.id, params={"doc_kind": doc_kind})
    db.add(job)
    db.flush()
    errors = []
    for i, f in enumerate(files):
        name = f.filename or "document"
        data = await f.read(s.CORPUS_MAX_UPLOAD_MB * 1024 * 1024 + 1)
        try:
            if len(data) > s.CORPUS_MAX_UPLOAD_MB * 1024 * 1024:
                raise ValidationError("too_large", "file too large")
            v = validate_upload(name, data)
        except ValidationError as exc:
            errors.append({"filename": name, "code": exc.code})
            continue
        rel = paths[i] if i < len(paths) else ""
        folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        db.add(CorpusJobItem(job_id=job.id, filename=v.safe_name, folder=folder[:300], file_type=v.file_type, storage_key=storage.save(data)))
        job.total += 1
    if not job.total:
        db.rollback()
        raise HTTPException(422, {"errors": errors})
    audit(db, "corpus_upload", user.id, "corpus_job", job.id, client_ip(request), files=job.total)
    db.commit()
    jobs.enqueue(job.id)
    db.refresh(job)
    return {"job": _job_out(job), "errors": errors}


class HarvestIn(BaseModel):
    sources: list[Literal["ojs", "openalex", "core", "crossref", "cyberleninka"]] = Field(min_length=1)
    queries: list[str] = Field(default_factory=list, max_length=50)
    ojs_urls: list[str] = Field(default_factory=list, max_length=100)
    limit: int = Field(50, ge=1, le=1000)
    fulltext: bool = True


@router.post("/harvest", status_code=201)
def harvest(body: HarvestIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    s = get_settings()
    queries = [q.strip() for q in body.queries if q.strip()] or csv_list(s.HARVEST_QUERIES)
    urls = [u.strip() for u in body.ojs_urls if u.strip().startswith(("http://", "https://"))] or csv_list(s.HARVEST_OJS_URLS)
    if "ojs" in body.sources and not urls:
        raise HTTPException(422, "no_ojs_urls")
    if any(src != "ojs" for src in body.sources) and not queries:
        raise HTTPException(422, "no_queries")
    job = CorpusJob(kind="harvest", created_by=user.id, params={**body.model_dump(), "queries": queries, "ojs_urls": urls})
    db.add(job)
    audit(db, "corpus_harvest", user.id, "corpus_job", None, client_ip(request), sources=body.sources)
    db.commit()
    jobs.enqueue(job.id)
    db.refresh(job)
    return _job_out(job)


@router.get("/settings")
def harvest_settings(_: User = Depends(get_current_user)):
    s = get_settings()
    return {
        "sources": list(HARVESTERS), "queries": csv_list(s.HARVEST_QUERIES), "ojs_urls": csv_list(s.HARVEST_OJS_URLS),
        "limit": s.HARVEST_MAX_PER_SOURCE, "fulltext": s.HARVEST_FETCH_FULLTEXT,
        "core_configured": bool(s.CORE_API_KEY.get_secret_value()), "brave_configured": bool(s.BRAVE_API_KEY.get_secret_value()),
        "doc_kinds": list(DOC_KINDS),
    }


@router.get("/jobs")
def list_jobs(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [_job_out(j) for j in db.scalars(select(CorpusJob).order_by(CorpusJob.created_at.desc()).limit(30)).all()]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    j = db.get(CorpusJob, job_id)
    if j is None:
        raise HTTPException(404, "not_found")
    return _job_out(j)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    j = db.get(CorpusJob, job_id)
    if j is None:
        raise HTTPException(404, "not_found")
    if j.status in ("queued", "running"):
        j.status = "cancelled"
        for it in j.items:
            if it.status == "queued" and it.storage_key:
                storage.delete(it.storage_key)
                it.storage_key, it.status = None, "skipped"
        db.commit()
    return _job_out(j)
