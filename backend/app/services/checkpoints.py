"""Encrypted checkpoints so long analyses can resume where they stopped.

The expensive, restartable work for large dissertations is text extraction and
especially OCR (hundreds of pages). Checkpoints are keyed by document id and
file hash, stored next to the encrypted uploads, encrypted with the same key,
and deleted together with the document.
"""
from __future__ import annotations

import json
from pathlib import Path

from cryptography.fernet import InvalidToken

from app.core.config import get_settings
from app.core.security import get_fernet
from app.document_processing.types import Block, ExtractedDocument

EXTRACT_VERSION = "v2"


def _dir() -> Path:
    d = Path(get_settings().STORAGE_DIR) / "checkpoints"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(document_id: str, sha256: str, name: str) -> Path:
    if not document_id.isalnum() or not sha256.isalnum() or not name.isalnum():
        raise ValueError("invalid checkpoint key")
    return _dir() / f"{document_id}-{sha256[:16]}-{name}.ckpt"


def save(document_id: str, sha256: str, name: str, obj) -> None:
    path = _key(document_id, sha256, name)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(get_fernet().encrypt(json.dumps(obj, ensure_ascii=False).encode("utf-8")))
    tmp.replace(path)


def load(document_id: str, sha256: str, name: str):
    path = _key(document_id, sha256, name)
    if not path.exists():
        return None
    try:
        return json.loads(get_fernet().decrypt(path.read_bytes()).decode("utf-8"))
    except (InvalidToken, ValueError):
        path.unlink(missing_ok=True)  # corrupt or written with another key: redo the work
        return None


def delete_document(document_id: str) -> None:
    if not document_id.isalnum():
        return
    for p in _dir().glob(f"{document_id}-*"):
        p.unlink(missing_ok=True)


def dump_extracted(doc: ExtractedDocument) -> dict:
    return {
        "version": EXTRACT_VERSION,
        "file_type": doc.file_type,
        "page_count": doc.page_count,
        "pages_estimated": doc.pages_estimated,
        "is_scanned": doc.is_scanned,
        "ocr_used": doc.ocr_used,
        "warnings": doc.warnings,
        "hidden": doc.hidden_fragments,
        "blocks": [[b.text, b.kind, b.page, b.heading_level, b.style, b.is_ocr] for b in doc.blocks],
    }


def restore_extracted(data: dict | None) -> ExtractedDocument | None:
    if not data or data.get("version") != EXTRACT_VERSION:
        return None
    blocks = [Block(i, t, k, p, h, s, o) for i, (t, k, p, h, s, o) in enumerate(data["blocks"])]
    return ExtractedDocument(
        data["file_type"], blocks, data["page_count"], data["pages_estimated"], data["is_scanned"], data["ocr_used"], data["warnings"],
        data.get("hidden", []),
    )
