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
    if len(files) > 500:
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


CORPUS_EXTS = {"docx": "docx", "pdf": "pdf", "txt": "txt"}
ZIP_MAX_RATIO = 200  # an entry that expands more than this is treated as a zip bomb


@router.post("/upload-zip", status_code=201)
async def upload_zip(
    request: Request,
    file: UploadFile = File(...),
    doc_kind: str = Form("other"),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """One ZIP archive with hundreds of DOCX/PDF/TXT files (folders inside are kept as the "folder")."""
    import zipfile

    s = get_settings()
    if doc_kind not in DOC_KINDS:
        raise HTTPException(422, "invalid_doc_kind")
    size = file.file.seek(0, 2)
    file.file.seek(0)
    if size > s.CORPUS_MAX_ZIP_MB * 1024 * 1024:
        raise HTTPException(413, "zip_too_large")
    try:
        zf = zipfile.ZipFile(file.file)
    except zipfile.BadZipFile as exc:
        raise HTTPException(422, "bad_zip") from exc
    job = CorpusJob(kind="ingest", created_by=user.id, params={"doc_kind": doc_kind, "zip": file.filename})
    db.add(job)
    db.flush()
    errors, total_bytes = [], 0
    limit = s.CORPUS_MAX_UPLOAD_MB * 1024 * 1024
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        base = name.rsplit("/", 1)[-1]
        if info.is_dir() or name.startswith("__MACOSX/") or base.startswith((".", "~$")):
            continue
        if base.rsplit(".", 1)[-1].lower() not in CORPUS_EXTS:
            continue
        if job.total >= s.CORPUS_MAX_FILES_PER_IMPORT:
            errors.append({"filename": name, "code": "too_many_files"})
            break
        if info.file_size > limit or (info.compress_size and info.file_size / info.compress_size > ZIP_MAX_RATIO):
            errors.append({"filename": name, "code": "too_large" if info.file_size > limit else "zip_bomb"})
            continue
        total_bytes += info.file_size
        if total_bytes > 4 * s.CORPUS_MAX_ZIP_MB * 1024 * 1024:
            errors.append({"filename": name, "code": "archive_too_large_uncompressed"})
            break
        data = zf.read(info)
        try:
            v = validate_upload(base, data)
        except ValidationError as exc:
            errors.append({"filename": name, "code": exc.code})
            continue
        folder = name.rsplit("/", 1)[0] if "/" in name else ""
        db.add(CorpusJobItem(job_id=job.id, filename=v.safe_name, folder=folder[:300], file_type=v.file_type, storage_key=storage.save(data)))
        job.total += 1
    if not job.total:
        db.rollback()
        raise HTTPException(422, {"errors": errors or [{"filename": file.filename, "code": "no_documents"}]})
    audit(db, "corpus_upload", user.id, "corpus_job", job.id, client_ip(request), files=job.total, zip=True)
    db.commit()
    jobs.enqueue(job.id)
    db.refresh(job)
    return {"job": _job_out(job), "errors": errors}


class FolderIn(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    doc_kind: str = "other"


@router.post("/import-folder", status_code=201)
def import_folder(body: FolderIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Index every DOCX/PDF/TXT under a folder of this computer (local single-PC mode). Files are read in place:
    nothing is copied or deleted. Hundreds of files at once, e.g. C:\\Kutubxona\\Darsliklar."""
    import os
    from pathlib import Path

    s = get_settings()
    if not s.corpus_local_import:
        raise HTTPException(403, "local_import_disabled")
    if body.doc_kind not in DOC_KINDS:
        raise HTTPException(422, "invalid_doc_kind")
    root = Path(body.path.strip().strip('"')).expanduser()
    if not root.is_dir():
        raise HTTPException(422, "folder_not_found")
    root = root.resolve()
    job = CorpusJob(kind="ingest", created_by=user.id, params={"doc_kind": body.doc_kind, "root": str(root), "local": True})
    db.add(job)
    db.flush()
    skipped = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        rel = Path(dirpath).relative_to(root).as_posix()
        for fn in sorted(filenames):
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
            if ext not in CORPUS_EXTS or fn.startswith(("~$", ".")):
                continue
            if job.total >= s.CORPUS_MAX_FILES_PER_IMPORT:
                skipped += 1
                continue
            db.add(CorpusJobItem(job_id=job.id, filename=fn[:300], folder=("" if rel == "." else rel)[:300], file_type=CORPUS_EXTS[ext]))
            job.total += 1
    if not job.total:
        db.rollback()
        raise HTTPException(422, "no_documents_in_folder")
    audit(db, "corpus_import_folder", user.id, "corpus_job", job.id, client_ip(request), files=job.total)
    db.commit()
    jobs.enqueue(job.id)
    db.refresh(job)
    return {"job": _job_out(job), "skipped_over_limit": skipped}


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


@router.get("/modules")
def list_modules(words: int = Query(0, ge=0, le=5_000_000), _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Plagiarism modules with availability, defaults and (for ``words`` > 0) the per-module estimate."""
    from app.plagiarism import modules as plag_modules

    est = plag_modules.estimate(words, plag_modules.default_modules(), db)
    return {"modules": list(est["modules"].values()), "defaults": plag_modules.default_modules(), "estimate": est}


@router.get("/settings")
def harvest_settings(_: User = Depends(get_current_user)):
    s = get_settings()
    return {
        "sources": list(HARVESTERS), "queries": csv_list(s.HARVEST_QUERIES), "ojs_urls": csv_list(s.HARVEST_OJS_URLS),
        "limit": s.HARVEST_MAX_PER_SOURCE, "fulltext": s.HARVEST_FETCH_FULLTEXT,
        "core_configured": bool(s.CORE_API_KEY.get_secret_value()), "brave_configured": bool(s.BRAVE_API_KEY.get_secret_value()),
        "doc_kinds": list(DOC_KINDS),
        "local_import": s.corpus_local_import, "max_zip_mb": s.CORPUS_MAX_ZIP_MB, "max_files": s.CORPUS_MAX_FILES_PER_IMPORT,
        "ojs_auto_hours": s.OJS_AUTO_HARVEST_HOURS,
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
