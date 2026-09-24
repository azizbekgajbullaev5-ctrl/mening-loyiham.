"""Background corpus jobs: bulk ingestion of uploaded files and harvesting of open sources.

Runs on its own single worker thread so building the reference corpus does
not block document analyses. Jobs are persisted and resume after a restart.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import csv_list, get_settings
from app.core.database import SessionLocal
from app.document_processing.extractors import extract
from app.models import CorpusJob, CorpusJobItem, RefDocument
from app.plagiarism import corpus
from app.plagiarism.harvest.sources import HARVESTERS
from app.services import storage

log = logging.getLogger(__name__)
_executor: ThreadPoolExecutor | None = None
_lock = threading.Lock()


def enqueue(job_id: str) -> None:
    s = get_settings()
    if s.TASK_MODE == "inline":
        run_job(job_id)
        return
    global _executor
    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="corpus")
    _executor.submit(run_job, job_id)


def run_job(job_id: str) -> None:
    try:
        with SessionLocal() as db:
            job = db.get(CorpusJob, job_id)
            if job is None or job.status in ("completed", "cancelled"):
                return
            job.status = "running"
            db.commit()
            if job.kind == "ingest":
                _run_ingest(db, job)
            else:
                _run_harvest(db, job)
            job = db.get(CorpusJob, job_id)
            if job.status == "running":
                job.status = "completed"
            job.finished_at = datetime.now(UTC)
            db.commit()
    except Exception as exc:  # noqa: BLE001
        log.exception("corpus job %s failed", job_id)
        with SessionLocal() as db:
            job = db.get(CorpusJob, job_id)
            if job:
                job.status, job.message = "failed", f"{exc.__class__.__name__}: {exc}"[:300]
                job.finished_at = datetime.now(UTC)
                db.commit()


def _log(job: CorpusJob, msg: str) -> None:
    job.log = (list(job.log or []) + [msg[:200]])[-200:]
    job.message = msg[:300]


def _run_ingest(db, job: CorpusJob) -> None:
    items = db.scalars(select(CorpusJobItem).where(CorpusJobItem.job_id == job.id, CorpusJobItem.status == "queued")).all()
    for it in items:
        db.refresh(job)
        if job.status == "cancelled":
            return
        try:
            data = storage.load(it.storage_key)
            doc = extract(it.file_type, data)
            texts = corpus.body_texts(doc)
            title = next((b.text for b in doc.blocks[:5] if b.kind == "heading" and 3 <= len(b.text) <= 300), None) or it.filename.rsplit(".", 1)[0]
            ref = corpus.ingest(db, texts, {**(job.params or {}), "title": title, "filename": it.filename, "folder": it.folder, "source_type": "upload"}, job.created_by)
            it.status, it.ref_doc_id = "added", ref.id
            job.added += 1
            _log(job, f"+ {it.filename}")
        except corpus.DuplicateDocument as dup:
            it.status, it.ref_doc_id = "skipped", dup.existing_id
            job.skipped += 1
            _log(job, f"= {it.filename} (dublikat)")
        except Exception as exc:  # noqa: BLE001 - one bad file must not stop the batch
            db.rollback()
            it = db.get(CorpusJobItem, it.id)
            job = db.get(CorpusJob, job.id)
            it.status, it.error = "failed", str(getattr(exc, "code", "") or exc)[:300]
            job.failed += 1
            _log(job, f"! {it.filename}: {it.error}")
        finally:
            storage.delete(it.storage_key)  # the original is never kept
            it.storage_key = None
            job.done += 1
            db.commit()


def _run_harvest(db, job: CorpusJob) -> None:
    s = get_settings()
    p = job.params or {}
    limit = int(p.get("limit") or s.HARVEST_MAX_PER_SOURCE)
    fulltext = bool(p.get("fulltext", s.HARVEST_FETCH_FULLTEXT))
    plan: list[tuple[str, str]] = []
    for src in p.get("sources", []):
        targets = p.get("ojs_urls") or csv_list(s.HARVEST_OJS_URLS) if src == "ojs" else p.get("queries") or csv_list(s.HARVEST_QUERIES)
        plan += [(src, t) for t in targets]
    job.total = len(plan) * limit
    db.commit()
    from app.plagiarism.web import Fetcher

    fetcher = Fetcher()
    for src, target in plan:
        harvester = HARVESTERS[src]()
        _log(job, f"{src}: {target}")
        db.commit()
        try:
            for item in harvester.harvest(target, limit):
                db.refresh(job)
                if job.status == "cancelled":
                    return
                _ingest_item(db, job, item, fulltext, fetcher, s.HARVEST_MIN_TEXT_CHARS)
                job.done += 1
                db.commit()
        except Exception as exc:  # noqa: BLE001 - network/API errors are logged per source
            db.rollback()
            job = db.get(CorpusJob, job.id)
            job.failed += 1
            _log(job, f"! {src} {target}: {exc.__class__.__name__}: {str(exc)[:120]}")
            db.commit()


def _ingest_item(db, job: CorpusJob, item, fulltext: bool, fetcher, min_chars: int) -> None:
    if item.doi and db.scalar(select(RefDocument.id).where(RefDocument.doi == item.doi.lower())):
        job.skipped += 1
        return
    if item.url and db.scalar(select(RefDocument.id).where(RefDocument.source_url == item.url)):
        job.skipped += 1
        return
    texts = [item.text]
    is_full = item.fulltext
    if fulltext and not is_full and item.pdf_url:
        try:
            ctype, data = fetcher.fetch_bytes(item.pdf_url)
            if "pdf" in ctype or data[:5] == b"%PDF-":
                texts = corpus.body_texts(extract("pdf", data))
                is_full = True
        except Exception as exc:  # noqa: BLE001 - fall back to title+abstract
            _log(job, f"  (to'liq matn olinmadi: {exc.__class__.__name__})")
    if sum(len(t) for t in texts) < min_chars:
        job.skipped += 1
        return
    try:
        corpus.ingest(db, texts, {"title": item.title, "authors": item.authors, "year": item.year, "doi": item.doi,
                                  "source_url": item.url, "source_type": item.source_type, "doc_kind": "article", "fulltext": is_full}, job.created_by)
        job.added += 1
        _log(job, f"+ {item.title[:120]}")
    except corpus.DuplicateDocument:
        job.skipped += 1
    except ValueError:
        job.skipped += 1


def recover() -> None:
    with SessionLocal() as db:
        ids = [j.id for j in db.scalars(select(CorpusJob).where(CorpusJob.status.in_(("queued", "running")))).all()]
    for jid in ids:
        enqueue(jid)
