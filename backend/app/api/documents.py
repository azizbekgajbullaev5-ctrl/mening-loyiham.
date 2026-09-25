from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user, owned_document
from app.api.serializers import analysis_summary, document_out
from app.core.config import get_settings
from app.core.database import get_db
from app.document_processing.structure import SECTION_KINDS
from app.document_processing.types import ExtractionError
from app.document_processing.validation import ValidationError, validate_upload
from app.models import Analysis, Document, DocumentFingerprint, DocumentVersion, User
from app.services import checkpoints, storage
from app.services.audit import audit
from app.plagiarism import modules as plag_modules
from app.plagiarism import web as webcheck
from app.plagiarism.textnorm import display_text
from app.services.pipeline import prepare
from app.tasks.queue import enqueue_analysis

router = APIRouter(prefix="/documents", tags=["documents"])

DOC_TYPES = ("phd_dissertation", "masters_dissertation", "textbook", "study_guide", "article", "conference_paper", "report")
Depth = Literal["quick", "standard", "deep"]


async def _read_limited(f: UploadFile, limit: int) -> bytes:
    chunks, total = [], 0
    while True:
        chunk = await f.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(413, "file_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


def apply_modules(db: Session, analysis: Analysis, keys: list[str], word_count) -> bool:
    """Set the enabled modules. Returns True when the analysis must wait for the user's confirmation
    (an online module is enabled): requests and approximate price per module are shown first."""
    analysis.check_modules = keys
    analysis.corpus_check, analysis.web_check = "corpus" in keys, "web" in keys
    online = [k for k in keys if k in plag_modules.ONLINE and plag_modules.availability(k, db)[0]]
    if not online:
        return False
    analysis.status, analysis.stage = "awaiting_confirmation", "awaiting_confirmation"
    analysis.web_estimate = plag_modules.estimate(word_count(), keys, db)
    return True


@router.post("", status_code=201)
async def upload(
    request: Request,
    files: list[UploadFile] = File(...),
    depth: Depth = Form("standard"),
    doc_type: str = Form("article"),
    keep_for_similarity: bool = Form(True),
    corpus_check: bool = Form(True),
    web_check: bool = Form(False),
    modules: str | None = Form(None),  # comma-separated module keys; overrides corpus_check/web_check
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    s = get_settings()
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, "invalid_doc_type")
    if not files or len(files) > s.MAX_FILES_PER_UPLOAD:
        raise HTTPException(422, "too_many_files")
    created, errors, to_run = [], [], []
    for f in files:
        name = f.filename or "document"
        try:
            data = await _read_limited(f, s.max_upload_bytes)
            v = validate_upload(name, data)
        except ValidationError as exc:
            errors.append({"filename": name, "code": exc.code, "message": str(exc)})
            continue
        except HTTPException as exc:
            errors.append({"filename": name, "code": exc.detail, "message": exc.detail})
            continue
        key = storage.save(data)
        doc = Document(
            owner_id=user.id, original_filename=v.safe_name, file_type=v.file_type, doc_type=doc_type,
            size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), storage_key=key, keep_for_similarity=keep_for_similarity,
        )
        db.add(doc)
        db.flush()
        version = DocumentVersion(document_id=doc.id, version_no=1)
        db.add(version)
        db.flush()
        analysis = Analysis(document_id=doc.id, version_id=version.id, owner_id=user.id, depth=depth)
        keys = plag_modules.normalize(modules.split(",")) if modules is not None else plag_modules.from_legacy(corpus_check, web_check)
        waiting = apply_modules(db, analysis, keys, lambda: webcheck.quick_word_count(v.file_type, data))
        db.add(analysis)
        db.flush()
        audit(db, "document_uploaded", user.id, "document", doc.id, client_ip(request), size=len(data), type=v.file_type)
        created.append((doc, analysis))
        if not waiting:
            to_run.append(analysis.id)
    db.commit()
    for aid in to_run:
        enqueue_analysis(aid)
    out = []
    for doc, analysis in created:
        db.refresh(doc)
        db.refresh(analysis)
        out.append({"document": document_out(doc), "analysis": analysis_summary(analysis)})
    if not created and errors:
        raise HTTPException(422, {"errors": errors})
    return {"items": out, "errors": errors}


@router.get("")
def list_documents(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs = db.scalars(select(Document).where(Document.owner_id == user.id).order_by(Document.created_at.desc())).all()
    return [document_out(d) for d in docs]


@router.get("/{document_id}")
def get_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = owned_document(db, user, document_id)
    out = document_out(d)
    out["analyses"] = [analysis_summary(a) for a in reversed(d.analyses)]
    return out


@router.delete("/{document_id}")
def delete_document(document_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Permanently delete the file, its fingerprints and every analysis/report."""
    d = owned_document(db, user, document_id)
    storage.delete(d.storage_key)
    checkpoints.delete_document(d.id)
    db.execute(delete(DocumentFingerprint).where(DocumentFingerprint.document_id == d.id))
    audit(db, "document_deleted", user.id, "document", d.id, client_ip(request))
    db.delete(d)
    db.commit()
    return {"ok": True}


@router.delete("/{document_id}/file")
def delete_document_file(document_id: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete only the stored original file; analysis results are kept."""
    d = owned_document(db, user, document_id)
    storage.delete(d.storage_key)
    checkpoints.delete_document(d.id)
    d.storage_key, d.file_deleted_at = None, datetime.now(UTC)
    audit(db, "document_file_deleted", user.id, "document", d.id, client_ip(request))
    db.commit()
    return {"ok": True}


def _load_prepared(d: Document):
    if not d.storage_key or not storage.exists(d.storage_key):
        raise HTTPException(410, "file_deleted")
    version = d.versions[-1] if d.versions else None
    manual = version.structure if version and version.structure_source == "manual" else None
    try:
        # the extraction checkpoint makes re-opening large documents fast
        return prepare(d.file_type, storage.load(d.storage_key), manual, checkpoint=(d.id, d.sha256))
    except ExtractionError as exc:
        raise HTTPException(422, exc.code) from exc


@router.get("/{document_id}/content")
def document_content(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Paragraphs of the document (re-extracted on demand from the encrypted file; not stored in the DB)."""
    d = owned_document(db, user, document_id)
    prep = _load_prepared(d)
    heading_at = {h.paragraph_index: h for h in prep.headings}
    blocks = prep.doc.blocks[:8000]
    return {
        "language": prep.language,
        "paragraphs": [
            {
                "index": b.index, "number": b.index + 1, "text": display_text(b.text), "kind": b.kind, "page": b.page,
                "heading": {"kind": heading_at[b.index].kind, "level": heading_at[b.index].level} if b.index in heading_at else None,
            }
            for b in blocks
        ],
        "truncated": len(prep.doc.blocks) > len(blocks),
    }


class HeadingIn(BaseModel):
    paragraph_index: int = Field(ge=0)
    kind: str
    level: int = Field(ge=1, le=3)
    title: str = Field(max_length=300)


class StructureIn(BaseModel):
    headings: list[HeadingIn] = Field(max_length=2000)
    reanalyze: bool = True
    depth: Depth = "standard"


@router.get("/{document_id}/structure")
def get_structure(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = owned_document(db, user, document_id)
    v = d.versions[-1] if d.versions else None
    return {"headings": v.structure if v else [], "source": v.structure_source if v else "auto", "paragraph_count": v.paragraph_count if v else 0, "kinds": SECTION_KINDS}


@router.put("/{document_id}/structure")
def put_structure(document_id: str, body: StructureIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Manually correct the detected structure; optionally re-run the analysis with it."""
    d = owned_document(db, user, document_id)
    prev = d.versions[-1] if d.versions else None
    n = prev.paragraph_count if prev else 0
    seen = set()
    for h in body.headings:
        if h.kind not in SECTION_KINDS or h.kind == "front_matter":
            raise HTTPException(422, f"invalid_kind:{h.kind}")
        if n and h.paragraph_index >= n:
            raise HTTPException(422, "paragraph_index_out_of_range")
        if h.paragraph_index in seen:
            raise HTTPException(422, "duplicate_paragraph_index")
        seen.add(h.paragraph_index)
    if body.reanalyze and not d.storage_key:
        raise HTTPException(410, "file_deleted")
    v = DocumentVersion(
        document_id=d.id, version_no=(prev.version_no + 1) if prev else 1, structure_source="manual",
        structure=[h.model_dump() for h in sorted(body.headings, key=lambda h: h.paragraph_index)],
    )
    if prev:
        for f in ("page_count", "pages_estimated", "word_count", "char_count", "paragraph_count", "language", "language_confidence",
                  "language_distribution", "is_scanned", "ocr_used", "warnings"):
            setattr(v, f, getattr(prev, f))
    db.add(v)
    db.flush()
    audit(db, "structure_corrected", user.id, "document", d.id, client_ip(request), headings=len(body.headings))
    analysis = None
    waiting = False
    if body.reanalyze:
        analysis = Analysis(document_id=d.id, version_id=v.id, owner_id=user.id, depth=body.depth)
        waiting = apply_modules(db, analysis, _previous_modules(d), lambda: v.word_count or 0)
        db.add(analysis)
    db.commit()
    if analysis and not waiting:
        enqueue_analysis(analysis.id)
        db.refresh(analysis)
    return {"version_id": v.id, "analysis": analysis_summary(analysis) if analysis else None}


class ReanalyzeIn(BaseModel):
    depth: Depth = "standard"
    modules: list[str] | None = None  # default: the modules of the previous analysis


def _previous_modules(d: Document) -> list[str]:
    last = d.analyses[-1] if d.analyses else None
    return plag_modules.enabled_for(last) if last else plag_modules.default_modules()


@router.post("/{document_id}/analyses", status_code=201)
def reanalyze(document_id: str, body: ReanalyzeIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    d = owned_document(db, user, document_id)
    if not d.storage_key:
        raise HTTPException(410, "file_deleted")
    v = d.versions[-1] if d.versions else None
    a = Analysis(document_id=d.id, version_id=v.id if v else None, owner_id=user.id, depth=body.depth)
    keys = plag_modules.normalize(body.modules) if body.modules is not None else _previous_modules(d)
    waiting = apply_modules(db, a, keys, lambda: (v.word_count if v else 0) or 0)
    db.add(a)
    audit(db, "analysis_requested", user.id, "document", d.id, client_ip(request), depth=body.depth, modules=keys)
    db.commit()
    if not waiting:
        enqueue_analysis(a.id)
    db.refresh(a)
    return analysis_summary(a)
