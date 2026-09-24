"""Reference corpus ("ma'lumotnoma bazasi").

Documents are reduced to (1) winnowed shingle fingerprints with token
positions and (2) chunk embedding vectors plus a document centroid. The text
itself is discarded after indexing.
"""
from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analyzers.languages.registry import detect_distribution
from app.core.config import get_settings
from app.core.database import engine
from app.document_processing.structure import build_sections, detect_headings
from app.document_processing.types import ExtractedDocument
from app.models import RefDocument, RefFingerprint, RefVector
from app.plagiarism import embeddings
from app.plagiarism.fingerprint import shingles, winnow
from app.plagiarism.textnorm import canonical_stopwords, display_text, tokenize

EXCLUDED_KINDS = {"references", "toc", "title", "appendix", "keywords"}
MIN_WORDS = 60


@dataclass
class IndexedText:
    canon: list[str]
    words: list[str]  # display words (original script) — used for embeddings
    fingerprints: list[tuple[int, int]]
    content_hash: str


def body_texts(doc: ExtractedDocument) -> list[str]:
    """Paragraph texts without references/TOC/title/tables (they cause false matches)."""
    paras = [b.text for b in doc.blocks if b.kind != "table"]
    lang, _, _ = detect_distribution(paras[:400])
    sections = build_sections(detect_headings(doc.blocks, lang), len(doc.blocks), doc.blocks)
    excluded: set[int] = set()
    for s in sections:
        if s.kind in EXCLUDED_KINDS:
            excluded.update(range(s.start, s.end))
    heading_idx = {s.start for s in sections if s.kind != "front_matter"}
    return [b.text for b in doc.blocks if b.kind != "table" and b.index not in excluded and b.index not in heading_idx]


def index_text(texts: list[str]) -> IndexedText:
    canon: list[str] = []
    words: list[str] = []
    for t in texts:
        disp = display_text(t)
        for tok in tokenize(disp):
            canon.append(tok.text)
            words.append(disp[tok.start : tok.end])
    fps = winnow(shingles(canon, canonical_stopwords()))
    digest = hashlib.sha256(" ".join(canon).encode("utf-8")).hexdigest()
    return IndexedText(canon, words, fps, digest)


def embed_chunks(ix: IndexedText) -> tuple[str, int, list[tuple[int, np.ndarray]]]:
    be = embeddings.get_backend()
    spans = embeddings.chunk_windows(ix.canon)
    source = ix.canon if isinstance(be, embeddings.HashBackend) else ix.words
    texts = [" ".join(source[a:b]) for a, b in spans]
    out: list[tuple[int, np.ndarray]] = []
    for i in range(0, len(texts), 256):
        vecs = be.encode(texts[i : i + 256])
        out.extend((spans[i + j][0], vecs[j]) for j in range(len(vecs)))
    return be.id, be.dims, out


class DuplicateDocument(Exception):
    def __init__(self, existing_id: str):
        super().__init__(existing_id)
        self.existing_id = existing_id


def ingest(db: Session, texts: list[str], meta: dict, added_by: str | None = None) -> RefDocument:
    """Index texts into the corpus. Raises DuplicateDocument / ValueError(too short)."""
    ix = index_text(texts)
    if len(ix.canon) < MIN_WORDS:
        raise ValueError("too_short")
    existing = db.scalar(select(RefDocument.id).where(RefDocument.content_hash == ix.content_hash))
    if existing:
        raise DuplicateDocument(existing)
    doi = (meta.get("doi") or "").lower().removeprefix("https://doi.org/") or None
    if doi:
        existing = db.scalar(select(RefDocument.id).where(RefDocument.doi == doi))
        if existing:
            raise DuplicateDocument(existing)
    lang, _, _ = detect_distribution(texts[:200])
    backend_id, dims, vecs = embed_chunks(ix)
    centroid = None
    if vecs:
        c = np.mean(np.stack([v for _, v in vecs]), axis=0)
        n = np.linalg.norm(c)
        centroid = embeddings.to_blob(c / n if n else c)
    doc = RefDocument(
        title=(meta.get("title") or "Untitled")[:500], authors=(meta.get("authors") or "")[:500], year=meta.get("year"),
        doc_kind=meta.get("doc_kind") or "other", source_type=meta.get("source_type") or "upload",
        source_url=(meta.get("source_url") or None), doi=doi, language=lang, folder=(meta.get("folder") or "")[:300],
        filename=(meta.get("filename") or "")[:300], word_count=len(ix.canon), content_hash=ix.content_hash,
        fingerprint_count=len(ix.fingerprints), vector_count=len(vecs), vector_backend=f"{backend_id}|{dims}",
        centroid=centroid, fulltext=bool(meta.get("fulltext", True)), added_by=added_by,
    )
    db.add(doc)
    db.flush()
    db.execute(
        RefFingerprint.__table__.insert(),
        [{"ref_doc_id": doc.id, "hash": h, "pos": p} for h, p in ix.fingerprints],
    )
    if vecs:
        db.execute(
            RefVector.__table__.insert(),
            [{"ref_doc_id": doc.id, "chunk_index": i, "token_start": start, "vector": embeddings.to_blob(v)} for i, (start, v) in enumerate(vecs)],
        )
    db.commit()
    vector_index.invalidate()
    return doc


def delete_ref(db: Session, ref_id: str) -> bool:
    doc = db.get(RefDocument, ref_id)
    if doc is None:
        return False
    db.execute(delete(RefFingerprint).where(RefFingerprint.ref_doc_id == ref_id))
    db.execute(delete(RefVector).where(RefVector.ref_doc_id == ref_id))
    db.delete(doc)
    db.commit()
    vector_index.invalidate()
    return True


def stats(db: Session) -> dict:
    docs = db.scalar(select(func.count()).select_from(RefDocument)) or 0
    fps = db.scalar(select(func.coalesce(func.sum(RefDocument.fingerprint_count), 0))) or 0
    vecs = db.scalar(select(func.coalesce(func.sum(RefDocument.vector_count), 0))) or 0
    words = db.scalar(select(func.coalesce(func.sum(RefDocument.word_count), 0))) or 0
    by_kind = dict(db.execute(select(RefDocument.doc_kind, func.count()).group_by(RefDocument.doc_kind)).all())
    by_source = dict(db.execute(select(RefDocument.source_type, func.count()).group_by(RefDocument.source_type)).all())
    by_lang = dict(db.execute(select(RefDocument.language, func.count()).group_by(RefDocument.language)).all())
    return {
        "documents": int(docs), "fingerprints": int(fps), "vectors": int(vecs), "words": int(words),
        "by_kind": by_kind, "by_source": by_source, "by_language": by_lang,
        "database_bytes": _database_bytes(db), "embedding_backend": embeddings.get_backend().id,
    }


def _database_bytes(db: Session) -> int | None:
    url = str(engine.url)
    if url.startswith("sqlite:///"):
        p = Path(url.removeprefix("sqlite:///"))
        return sum(f.stat().st_size for f in (p, p.with_name(p.name + "-wal")) if f.exists())
    try:
        return int(db.scalar(select(func.pg_database_size(func.current_database()))))
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- lookups
def lookup_hashes(db: Session, hashes: list[int], max_docs_per_hash: int = 40) -> dict[int, list[tuple[str, int]]]:
    """hash -> [(ref_doc_id, pos)] for all hashes present in the corpus."""
    found: dict[int, list[tuple[str, int]]] = {}
    uniq = list(dict.fromkeys(hashes))
    for i in range(0, len(uniq), 900):
        rows = db.execute(
            select(RefFingerprint.hash, RefFingerprint.ref_doc_id, RefFingerprint.pos).where(RefFingerprint.hash.in_(uniq[i : i + 900]))
        ).all()
        for h, d, p in rows:
            lst = found.setdefault(h, [])
            if len(lst) < max_docs_per_hash:
                lst.append((d, p))
    return found


class VectorIndex:
    """In-memory matrix of document centroids for the current embedding backend."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self._loaded = -1
        self.ids: list[str] = []
        self.matrix: np.ndarray | None = None

    def invalidate(self) -> None:
        with self._lock:
            self._version += 1

    def centroids(self, db: Session) -> tuple[list[str], np.ndarray | None]:
        with self._lock:
            if self._loaded == self._version:
                return self.ids, self.matrix
            be = embeddings.get_backend()
            key = f"{be.id}|{be.dims}"
            rows = db.execute(select(RefDocument.id, RefDocument.centroid).where(RefDocument.vector_backend == key, RefDocument.centroid.is_not(None))).all()
            self.ids = [r[0] for r in rows]
            self.matrix = np.vstack([embeddings.from_blob(r[1], be.dims) for r in rows]) if rows else None
            self._loaded = self._version
            return self.ids, self.matrix

    def chunk_vectors(self, db: Session, ref_ids: list[str]) -> tuple[list[tuple[str, int]], np.ndarray | None]:
        be = embeddings.get_backend()
        rows = db.execute(select(RefVector.ref_doc_id, RefVector.token_start, RefVector.vector).where(RefVector.ref_doc_id.in_(ref_ids))).all()
        if not rows:
            return [], None
        meta = [(r[0], r[1]) for r in rows]
        return meta, np.vstack([embeddings.from_blob(r[2], be.dims) for r in rows])


vector_index = VectorIndex()
