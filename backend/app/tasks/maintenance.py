"""Retention cleanup and recovery of interrupted jobs.

Run manually with ``python -m app.tasks.maintenance``; the API process also
runs it periodically when RETENTION_DAYS > 0.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Analysis, Document
from app.services import checkpoints, storage
from app.services.audit import audit

log = logging.getLogger(__name__)


def cleanup_expired_files() -> int:
    """Delete stored files older than RETENTION_DAYS (results and metadata are kept)."""
    days = get_settings().RETENTION_DAYS
    if days <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=days)
    n = 0
    with SessionLocal() as db:
        docs = db.scalars(select(Document).where(Document.storage_key.is_not(None), Document.created_at < cutoff)).all()
        for d in docs:
            storage.delete(d.storage_key)
            checkpoints.delete_document(d.id)
            d.storage_key, d.file_deleted_at = None, datetime.now(UTC)
            audit(db, "retention_file_deleted", d.owner_id, "document", d.id)
            n += 1
        db.commit()
    return n


def recover_interrupted() -> list[str]:
    """Re-queue analyses left queued/running by a restarted in-process worker."""
    with SessionLocal() as db:
        rows = db.scalars(select(Analysis).where(Analysis.status.in_(("queued", "running")))).all()
        ids = []
        for a in rows:
            a.status, a.stage, a.progress = "queued", "queued", 0
            ids.append(a.id)
        db.commit()
    return ids


def start_periodic_cleanup(interval_seconds: int = 3600) -> None:
    if get_settings().RETENTION_DAYS <= 0:
        return

    def loop() -> None:
        while True:
            try:
                cleanup_expired_files()
            except Exception:  # noqa: BLE001
                log.exception("cleanup failed")
            time.sleep(interval_seconds)

    threading.Thread(target=loop, daemon=True, name="retention-cleanup").start()


if __name__ == "__main__":
    print(f"deleted files: {cleanup_expired_files()}")
