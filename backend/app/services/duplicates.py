"""Earlier copies of the same document among the owner's uploads.

A re-uploaded file (same bytes), a file with the same name, or a file with (nearly) the same text is the
same work, not a source: comparing a document with its own earlier copy reports ~100% "borrowing".
Such copies are excluded from the own-documents comparison and reported as a warning instead.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import PurePath

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Document, DocumentFingerprint

# shared fingerprints / fingerprints of the LARGER document: a re-saved or lightly edited copy stays above this,
# while an earlier article reused as one chapter (a real, reportable overlap) does not
SAME_TEXT_OVERLAP = 0.9
# a same-named file counts as a copy only if the texts also overlap this much (two students' "dissertatsiya.docx"
# are different works and must still be compared)
SAME_NAME_OVERLAP = 0.5
_COPY_SUFFIX = re.compile(r"(\s*[\(\[]\d+[\)\]]|\s*[-_ ]?\s*(copy|kopiya|копия|nusxa(si)?))+$", re.I)


def normalize_name(filename: str) -> str:
    stem = PurePath(filename.replace("\\", "/")).stem.lower()
    stem = _COPY_SUFFIX.sub("", stem)
    return re.sub(r"[\s_.\-]+", " ", stem).strip()


def find_copies(db: Session, doc: Document, fingerprints: set[int]) -> list[dict]:
    """Other documents of the same owner with the same file, name or text (newest first).

    ``excluded`` marks the ones treated as copies of this document (left out of the comparison).
    """
    others = db.execute(
        select(Document.id, Document.original_filename, Document.sha256, Document.created_at)
        .where(Document.owner_id == doc.owner_id, Document.id != doc.id)
    ).all()
    if not others:
        return []
    name = normalize_name(doc.original_filename)
    reasons: dict[str, list[str]] = {}
    for oid, fname, sha, _ in others:
        r = []
        if sha == doc.sha256:
            r.append("same_file")
        if name and normalize_name(fname) == name:
            r.append("same_name")
        if r:
            reasons[oid] = r
    overlap: dict[str, float] = {}
    if fingerprints:
        shared: dict[str, set[int]] = defaultdict(set)
        fps = list(fingerprints)
        for i in range(0, len(fps), 900):
            for h, doc_id in db.execute(
                select(DocumentFingerprint.hash, DocumentFingerprint.document_id).where(
                    DocumentFingerprint.owner_id == doc.owner_id, DocumentFingerprint.document_id != doc.id,
                    DocumentFingerprint.hash.in_(fps[i : i + 900]),
                )
            ):
                shared[doc_id].add(h)
        if shared:
            sizes = dict(db.execute(
                select(DocumentFingerprint.document_id, func.count(func.distinct(DocumentFingerprint.hash)))
                .where(DocumentFingerprint.document_id.in_(list(shared)))
                .group_by(DocumentFingerprint.document_id)
            ).all())
            for doc_id, hs in shared.items():
                ratio = len(hs) / max(1, len(fingerprints), sizes.get(doc_id, 0))
                overlap[doc_id] = round(min(1.0, ratio), 3)
                if ratio >= SAME_TEXT_OVERLAP:
                    reasons.setdefault(doc_id, []).append("same_text")
    out = []
    for oid, fname, _sha, created in others:
        r = reasons.get(oid)
        if not r:
            continue
        ov = overlap.get(oid) or 0.0
        excluded = "same_file" in r or "same_text" in r or ("same_name" in r and ov >= SAME_NAME_OVERLAP)
        out.append({"id": oid, "filename": fname, "uploaded_at": created.isoformat() if created else None,
                    "reasons": r, "overlap": overlap.get(oid), "excluded": excluded})
    return sorted(out, key=lambda d: d["uploaded_at"] or "", reverse=True)
