"""Analysis pipeline orchestration.

UPLOAD → VALIDATION → EXTRACTION → LANGUAGE → STRUCTURE → SEGMENTATION →
AI-LIKELIHOOD → SIMILARITY → STYLE → PARAPHRASE → ACADEMIC → AGGREGATION.
(Report generation happens on demand from the stored results.)

Each stage reports progress to the Analysis row so the UI can show it.
Nothing is sent to external services unless DEEP analysis is selected and a
provider is configured; even then only a budgeted subset of passages is sent.
"""
from __future__ import annotations

import logging
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analyzers import ai_likelihood as ai
from app.analyzers import similarity as sim
from app.analyzers.academic import analyze_academic
from app.analyzers.languages.registry import get_profile
from app.analyzers.style import section_style_metrics, style_consistency
from app.analyzers.text_utils import cv, words
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.document_processing.extractors import extract
from app.document_processing.segmentation import Passage, segment
from app.document_processing.structure import SIMILARITY_EXCLUDED_KINDS, Heading, Section, build_sections, detect_headings
from app.document_processing.types import ExtractedDocument, ExtractionError
from app.models import (
    Analysis,
    AnalysisResult,
    Document,
    DocumentFingerprint,
    DocumentVersion,
    PassageAnalysis,
    PlagiarismResult,
    RefDocument,
    SectionResult,
    SimilarityMatch,
)
from app.providers import registry
from app.providers.base import PassageInput
from app.services import checkpoints, duplicates, storage

log = logging.getLogger(__name__)
CONF = ai.CONFIDENCE_ORDER


class Progress:
    """Throttled progress writer (separate short transactions)."""

    def __init__(self, analysis_id: str):
        self.analysis_id = analysis_id
        self._last = 0.0

    def __call__(self, pct: float, stage: str, message: str = "", force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last < 0.4:
            return
        self._last = now
        with SessionLocal() as db:
            a = db.get(Analysis, self.analysis_id)
            if a is None:
                return
            a.progress = int(max(a.progress, min(99, pct)))
            a.stage = stage
            a.message = message[:300]
            db.commit()


@dataclass
class Prepared:
    doc: ExtractedDocument
    language: str
    language_confidence: float
    distribution: dict
    headings: list[Heading]
    sections: list[Section]


def prepare(
    file_type: str,
    data: bytes | None,
    manual_structure: list[dict] | None = None,
    progress=None,
    checkpoint: tuple[str, str] | None = None,
) -> Prepared:
    """Extract + detect language/structure.

    ``checkpoint`` = (document_id, sha256): reuse a saved extraction (and saved
    OCR pages) so an interrupted analysis resumes instead of starting over.
    """
    doc = checkpoints.restore_extracted(checkpoints.load(*checkpoint, "extract")) if checkpoint else None
    if doc is not None:
        if progress:
            progress(25, "extracting", "checkpoint", force=True)
    else:
        if data is None:
            raise ExtractionError("file_unavailable", "The original file is not available")
        ocr_cache: dict[str, str] = (checkpoints.load(*checkpoint, "ocr") or {}) if checkpoint else {}
        pending: list[int] = []

        def on_ocr_page(pno: int, text: str) -> None:
            ocr_cache[str(pno)] = text
            pending.append(pno)
            if checkpoint and len(pending) >= 5:  # persist every few pages
                checkpoints.save(*checkpoint, "ocr", ocr_cache)
                pending.clear()

        try:
            doc = extract(
                file_type, data, (lambda f, s: progress(_extract_pct(f, s), "extracting", s)) if progress else None,
                ocr_cache=ocr_cache, on_ocr_page=on_ocr_page,
            )
        finally:
            if checkpoint and pending:
                checkpoints.save(*checkpoint, "ocr", ocr_cache)
        if checkpoint:
            checkpoints.save(*checkpoint, "extract", checkpoints.dump_extracted(doc))
    paras = [b.text for b in doc.blocks if b.kind != "table"]
    language, lconf, dist = registry.language_provider().detect(paras)
    if progress:
        progress(30, "language", language, force=True)
    if manual_structure:
        headings = [Heading(h["paragraph_index"], h["kind"], int(h["level"]), h["title"], h.get("number")) for h in manual_structure]
    else:
        headings = detect_headings(doc.blocks, language)
    sections = build_sections(headings, len(doc.blocks), doc.blocks)
    return Prepared(doc, language, lconf, dist, headings, sections)


def _extract_pct(fraction: float, message: str) -> float:
    # OCR of scanned books dominates the run time, so it gets a larger share of the bar
    return 5 + 55 * fraction if message.startswith("OCR") else 5 + 20 * fraction


def run_analysis(analysis_id: str) -> None:
    progress = Progress(analysis_id)
    started = time.monotonic()
    with SessionLocal() as db:
        a = db.get(Analysis, analysis_id)
        if a is None or a.status == "completed":
            return
        a.status, a.stage, a.progress = "running", "starting", 1
        a.started_at = datetime.now(UTC)
        a.attempts += 1
        a.error = None
        db.commit()
    try:
        with SessionLocal() as db:
            _run(db, analysis_id, progress)
            a = db.get(Analysis, analysis_id)
            a.status, a.stage, a.progress, a.message = "completed", "completed", 100, ""
            a.finished_at = datetime.now(UTC)
            a.duration_seconds = round(time.monotonic() - started, 2)
            db.commit()
            doc = db.get(Document, a.document_id)
            if get_settings().DELETE_FILES_AFTER_ANALYSIS and doc and doc.storage_key:
                storage.delete(doc.storage_key)
                checkpoints.delete_document(doc.id)
                doc.storage_key, doc.file_deleted_at = None, datetime.now(UTC)
                db.commit()
    except ExtractionError as exc:
        _fail(analysis_id, f"{exc.code}: {exc}")
    except Exception as exc:  # noqa: BLE001 — record any failure on the analysis row
        log.error("analysis %s failed: %s\n%s", analysis_id, exc, traceback.format_exc())
        _fail(analysis_id, f"internal_error: {exc.__class__.__name__}")
        raise


def mark_retrying(analysis_id: str, attempt: int) -> None:
    with SessionLocal() as db:
        a = db.get(Analysis, analysis_id)
        if a and a.status == "failed" and not (a.error or "").startswith(PERMANENT_ERRORS):
            a.status, a.stage, a.message = "queued", "queued", f"retry {attempt}"
            db.commit()


def reset_for_resume(db: Session, a: Analysis) -> None:
    """Put a failed/interrupted analysis back in the queue; checkpoints make it resume."""
    a.status, a.stage, a.message, a.error, a.finished_at = "queued", "queued", "resume", None, None


# extraction errors that a retry cannot fix
PERMANENT_ERRORS = ("unsupported_type", "parse_error", "encrypted", "no_text", "scanned_no_ocr", "file_unavailable")


def _fail(analysis_id: str, error: str) -> None:
    with SessionLocal() as db:
        a = db.get(Analysis, analysis_id)
        if a:
            a.status, a.stage, a.error = "failed", "failed", error[:2000]
            a.finished_at = datetime.now(UTC)
            db.commit()


def _run(db: Session, analysis_id: str, progress: Progress) -> None:
    s = get_settings()
    a = db.get(Analysis, analysis_id)
    doc = db.get(Document, a.document_id)
    version = db.get(DocumentVersion, a.version_id) if a.version_id else None
    if not doc.storage_key or not storage.exists(doc.storage_key):
        raise ExtractionError("file_unavailable", "The original file has been deleted; re-upload to analyse again")

    progress(3, "extracting", doc.original_filename, force=True)
    ckpt = (doc.id, doc.sha256)
    manual = version.structure if (version and version.structure_source == "manual") else None
    has_ckpt = checkpoints.load(*ckpt, "extract") is not None
    data = None if has_ckpt else storage.load(doc.storage_key)
    prep = prepare(doc.file_type, data, manual, progress, checkpoint=ckpt)
    del data
    profile = get_profile(prep.language)
    blocks = prep.doc.blocks
    sections = prep.sections
    sec_by_order = {x.order: x for x in sections}

    # ---- persist extraction metadata on the version
    if version is None:
        version = DocumentVersion(document_id=doc.id, version_no=1)
        db.add(version)
        db.flush()
        a.version_id = version.id
    version.page_count = prep.doc.page_count
    version.pages_estimated = prep.doc.pages_estimated
    version.word_count = sum(len(words(b.text)) for b in blocks)
    version.char_count = sum(len(b.text) for b in blocks)
    version.paragraph_count = len(blocks)
    version.language, version.language_confidence, version.language_distribution = prep.language, prep.language_confidence, prep.distribution
    version.is_scanned, version.ocr_used = prep.doc.is_scanned, prep.doc.ocr_used
    version.warnings = prep.doc.warnings
    if version.structure_source != "manual":
        version.structure = [h.to_dict() for h in prep.headings]
    db.commit()

    progress(38, "segmenting", "", force=True)
    passages = segment(blocks, sections, profile.abbreviations)

    # ---- AI-likelihood (local), chapter by chapter
    para_cv: dict[int, float | None] = {}
    for sec in sections:
        lens = [len(words(b.text)) for b in blocks[sec.start + 1 : sec.own_end] if b.kind == "paragraph"]
        para_cv[sec.order] = cv(lens) if len(lens) >= 4 else None
    to_score = [p for p in passages if not p.excluded_from_ai]
    if a.depth == "quick":
        to_score = _sample(to_score, s.QUICK_MAX_PASSAGES_PER_SECTION)
    by_chapter: dict[int | None, list[Passage]] = defaultdict(list)
    for p in to_score:
        by_chapter[p.chapter_order].append(p)
    scores: dict[int, ai.PassageScore] = {}
    memo: dict[str, ai.PassageScore] = {}  # duplicate chunks are scored once
    done = 0
    for ch_order, plist in by_chapter.items():
        title = sec_by_order[ch_order].title if ch_order in sec_by_order else ""
        progress(40 + 30 * done / max(1, len(to_score)), "ai_analysis", title[:120], force=True)
        for p in plist:
            if p.hash in memo:
                src = memo[p.hash]
                scores[p.id] = ai.PassageScore(src.score, src.confidence, list(src.characteristics), dict(src.metrics), dict(src.subscores), src.word_count)
            else:
                ctx = ai.SectionContext(paragraph_length_cv=para_cv.get(p.section_order))
                scores[p.id] = memo[p.hash] = ai.score_passage(p.text, profile, ctx, is_ocr=p.is_ocr)
            done += 1
            progress(40 + 30 * done / max(1, len(to_score)), "ai_analysis", title[:120])
    ordered = [scores[p.id] for p in to_score]
    ai.apply_style_shift(ordered, profile)

    # ---- external / LLM AI providers (DEEP only, budgeted)
    provider_scores: dict[int, list[dict]] = defaultdict(list)
    providers_used = [{"name": "local_stylometry", "kind": "local", "status": "used", "method": ai.METHOD_VERSION}]
    comparison: dict = {"providers": [], "summary": "single_method"}
    ext_ai = registry.external_ai_providers()
    if a.depth == "deep":
        candidates = sorted((p for p in to_score if scores[p.id].score is not None), key=lambda p: -scores[p.id].score)[: s.EXTERNAL_MAX_PASSAGES]
        inputs = [PassageInput(p.id, p.text, prep.language, p.hash) for p in candidates]
        for prov in ext_ai:
            if not prov.is_configured():
                providers_used.append({"name": prov.name, "kind": prov.kind, "status": "not_configured"})
                continue
            if not prov.supports(prep.language):
                providers_used.append({"name": prov.name, "kind": prov.kind, "status": "language_not_supported"})
                continue
            progress(70, "external_ai", prov.name, force=True)
            results = prov.analyze(inputs) if inputs else []
            ok = [r for r in results if r.score is not None]
            errors = sorted({r.error for r in results if r.error})
            for r in ok:
                provider_scores[r.passage_id].append({"provider": prov.name, "kind": prov.kind, "score": r.score, "confidence": r.confidence, "characteristics": r.characteristics, "explanation": r.explanation})
            local_same = [scores[r.passage_id].score for r in ok]
            comparison["providers"].append(
                {
                    "name": prov.name, "kind": prov.kind, "passages_sent": len(inputs), "passages_scored": len(ok),
                    "mean_score": round(sum(r.score for r in ok) / len(ok), 1) if ok else None,
                    "local_mean_same_passages": round(sum(local_same) / len(local_same), 1) if local_same else None,
                    "cached": sum(1 for r in ok if r.cached), "errors": errors[:5],
                }
            )
            providers_used.append({"name": prov.name, "kind": prov.kind, "status": "used" if ok else "failed", "errors": errors[:5]})
        means = [p["mean_score"] for p in comparison["providers"] if p["mean_score"] is not None]
        locals_ = [p["local_mean_same_passages"] for p in comparison["providers"] if p["local_mean_same_passages"] is not None]
        if means:
            allv = means + locals_[:1]
            spread = max(allv) - min(allv)
            comparison["spread"] = round(spread, 1)
            comparison["summary"] = "methods_vary" if spread >= 15 else "methods_broadly_agree"
    else:
        for prov in ext_ai:
            providers_used.append({"name": prov.name, "kind": prov.kind, "status": "not_used_depth" if prov.is_configured() else "not_configured"})

    # ---- similarity
    progress(72, "similarity", "", force=True)
    sim_passages = [
        sim.SimPassage(p.id, p.section_order, p.paragraph_start, p.page, p.text, excluded=sec_by_order[p.section_order].kind in SIMILARITY_EXCLUDED_KINDS)
        for p in passages
    ]
    # earlier copies of this same document (re-upload, same name + text, same text) are not "sources"
    own_fps = {h for h, _, _ in sim.fingerprints(sim_passages, profile.stopwords)}
    copies = duplicates.find_copies(db, doc, own_fps)
    skip_ids = {c["id"] for c in copies if c["excluded"]}
    corpus_index = None
    if a.depth in ("standard", "deep"):
        corpus_index = _corpus_index(db, doc, skip_ids)
    outcome = sim.analyze(sim_passages, profile.stopwords, corpus_index, run_paraphrase=a.depth != "quick")

    external_cov = None
    sim_scope = "local_only"
    ext_matches: list[SimilarityMatch] = []
    ext_sim = registry.external_similarity_providers()
    configured_sim = [p for p in ext_sim if p.is_configured()]
    for prov in ext_sim:
        if not prov.is_configured():
            providers_used.append({"name": prov.name, "kind": prov.kind, "status": "not_configured", "category": "similarity"})
    if a.depth == "deep" and configured_sim:
        inputs = [PassageInput(p.id, p.text, prep.language, p.hash) for p in passages if not sec_by_order[p.section_order].kind in SIMILARITY_EXCLUDED_KINDS]
        pmap = {p.id: p for p in passages}
        for prov in configured_sim:
            progress(80, "external_similarity", prov.name, force=True)
            res = prov.check(inputs)
            providers_used.append({"name": prov.name, "kind": prov.kind, "status": "failed" if res.error else "used", "category": "similarity", "errors": [res.error] if res.error else []})
            if res.error is None:
                sim_scope = "local_and_external"
                external_cov = res.coverage if external_cov is None else max(external_cov, res.coverage or 0)
                for src in res.sources[:300]:
                    p = pmap.get(src.passage_id)
                    if p is None:
                        continue
                    ext_matches.append(
                        SimilarityMatch(
                            analysis_id=a.id, match_type="external", provider=prov.name, section_order=p.section_order, page=p.page,
                            paragraph_index=p.paragraph_start, text=p.text[:1500], matched_text=src.matched_text, source_title=src.source_title,
                            source_url=src.source_url, similarity=round(src.similarity, 3),
                        )
                    )
            elif sim_scope == "local_only":
                sim_scope = "local_only_external_failed"
    elif a.depth != "deep" and configured_sim:
        sim_scope = "local_only_external_not_requested"

    # ---- plagiarism (reference corpus, own documents, internet, paraphrase)
    progress(80, "plagiarism", "", force=True)
    _plagiarism(db, a, doc, prep, profile, progress, copies)

    # ---- style
    progress(86, "style", "", force=True)
    section_texts = {sec.order: " ".join(b.text for b in blocks[sec.start + 1 : sec.end] if b.kind != "table") for sec in sections}
    style_input = []
    sec_metrics: dict[int, dict] = {}
    for sec in sections:
        if sec.excluded_from_ai:
            continue
        m = section_style_metrics(section_texts[sec.order], profile) if len(words(section_texts[sec.order])) >= 60 else {}
        sec_metrics[sec.order] = m
        if sec.level == min((x.level for x in sections if not x.excluded_from_ai), default=1) or sec.kind in {"section", "subsection"}:
            style_input.append({"order": sec.order, "title": sec.title, "word_count": len(words(section_texts[sec.order])), "metrics": m})
    # leaf-ish sections give the most informative comparison
    leaves = [x for x in style_input if not any(y.parent_order == x["order"] for y in sections)]
    style = style_consistency(leaves if len(leaves) >= 3 else style_input)

    # ---- academic writing
    progress(90, "academic", "", force=True)
    academic = analyze_academic(blocks, sections, profile, doc.doc_type)

    # ---- aggregation & persistence
    progress(94, "aggregating", "", force=True)
    _persist(db, a, doc, prep, passages, scores, provider_scores, outcome, ext_matches, external_cov, sim_scope,
             providers_used, comparison, style, academic, sec_metrics, profile)
    if doc.keep_for_similarity:
        _store_fingerprints(db, doc, sim_passages, profile.stopwords)
    db.commit()


def _plagiarism(db: Session, a: Analysis, doc: Document, prep: Prepared, profile, progress, copies: list[dict] | None = None) -> None:
    from app.plagiarism import integrity, matcher
    from app.plagiarism import web as webcheck

    step = lambda msg: progress(82, "plagiarism", msg)  # noqa: E731
    copies = copies or []
    skip_ids = {c["id"] for c in copies if c["excluded"]}
    web_sources, web_stats = None, None
    if a.web_check:
        # first pass (no paraphrase) tells which sentences are already found locally: those are not searched online
        pre, stream = matcher.compare(db, prep.doc.blocks, prep.sections, doc, a.corpus_check, None, step,
                                      run_paraphrase=False, exclude_own=skip_ids)
        covered = np.zeros(len(stream.canon), dtype=bool)
        by_block: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for i, (b, s0) in enumerate(zip(stream.block, stream.start)):
            by_block[b].append((s0, i))
        for blk, st, en, _src, _cls in pre.spans:
            for s0, i in by_block.get(blk, ()):
                if st <= s0 < en:
                    covered[i] = True
        planned = int((a.web_estimate or {}).get("queries") or webcheck.planned_queries(len(stream.canon)))
        web_sources, web_stats = webcheck.run(db, stream, covered, planned, progress=lambda m: progress(84, "web", m),
                                              abbreviations=profile.abbreviations)
    outcome, _ = matcher.compare(db, prep.doc.blocks, prep.sections, doc, a.corpus_check, web_sources, step, exclude_own=skip_ids)
    modules = dict(outcome.modules)
    modules["corpus_documents"] = db.scalar(select(func.count()).select_from(RefDocument)) if a.corpus_check else 0
    if copies:
        modules["duplicates"] = copies
    if web_stats is not None:
        matched = {src["url"]: src["index"] for src in outcome.sources if src["module"] == "web" and src.get("url")}
        for page in web_stats.get("pages", []):
            page["source_index"] = matched.get(page["url"])  # set when the page was found as a source
        modules["web"] = True  # the check ran, even if it found nothing or failed (errors are listed)
        modules["web_stats"] = web_stats
    db.execute(delete(PlagiarismResult).where(PlagiarismResult.analysis_id == a.id))
    db.add(PlagiarismResult(
        analysis_id=a.id, checked_words=outcome.checked_words, excluded_words=outcome.excluded_words,
        originality=outcome.originality, borrowing=outcome.borrowing, citation=outcome.citation,
        paraphrase_share=outcome.paraphrase_share, sources=outcome.sources, spans=outcome.spans[:200000],
        integrity=integrity.scan(prep.doc), modules=modules, exclusions=outcome.exclusions,
    ))
    db.commit()


def _sample(passages: list[Passage], per_section: int) -> list[Passage]:
    groups: dict[int, list[Passage]] = defaultdict(list)
    for p in passages:
        groups[p.section_order].append(p)
    out = []
    for plist in groups.values():
        if len(plist) <= per_section:
            out.extend(plist)
        else:
            step = len(plist) / per_section
            out.extend(plist[int(i * step)] for i in range(per_section))
    return sorted(out, key=lambda p: p.id)


def _corpus_index(db: Session, doc: Document, skip_ids: set[str] = frozenset()) -> dict[int, list[tuple[str, int, int | None]]]:
    q = select(DocumentFingerprint.hash, DocumentFingerprint.document_id, DocumentFingerprint.paragraph_index, DocumentFingerprint.page).where(
        DocumentFingerprint.owner_id == doc.owner_id, DocumentFingerprint.document_id != doc.id
    )
    if skip_ids:
        q = q.where(DocumentFingerprint.document_id.not_in(list(skip_ids)))
    rows = db.execute(q).all()
    idx: dict[int, list[tuple[str, int, int | None]]] = defaultdict(list)
    for h, d, para, page in rows:
        idx[h].append((d, para, page))
    return idx


def _store_fingerprints(db: Session, doc: Document, sim_passages, stop) -> None:
    db.execute(delete(DocumentFingerprint).where(DocumentFingerprint.document_id == doc.id))
    fps = sim.fingerprints(sim_passages, stop)
    db.bulk_insert_mappings(
        DocumentFingerprint,
        [{"document_id": doc.id, "owner_id": doc.owner_id, "hash": h, "paragraph_index": para, "page": page} for h, para, page in fps],
    )


def _level_conf(levels: list[str], cap: str) -> str:
    if not levels:
        return "low"
    ranks = sorted(CONF.index(x) for x in levels)
    med = ranks[(len(ranks) - 1) // 2]  # lower median: conservative
    return CONF[min(med, CONF.index(cap))]


def _persist(db, a, doc, prep: Prepared, passages, scores, provider_scores, outcome, ext_matches, external_cov, sim_scope,
             providers_used, comparison, style, academic, sec_metrics, profile) -> None:
    s = get_settings()
    threshold = s.SUSPICIOUS_THRESHOLD
    blocks = prep.doc.blocks
    sections = prep.sections
    db.execute(delete(SectionResult).where(SectionResult.analysis_id == a.id))
    db.execute(delete(PassageAnalysis).where(PassageAnalysis.analysis_id == a.id))
    db.execute(delete(SimilarityMatch).where(SimilarityMatch.analysis_id == a.id))
    db.execute(delete(AnalysisResult).where(AnalysisResult.analysis_id == a.id))

    pmap = {p.id: p for p in passages}
    scored = [(pmap[pid], sc) for pid, sc in scores.items() if sc.score is not None]
    flagged = [(p, sc) for p, sc in scored if sc.score >= threshold]
    total_scored_words = sum(p.word_count for p, _ in scored)

    # ---- per-section aggregation (sections include their children)
    for sec in sections:
        in_sec = [(p, sc) for p, sc in scored if sec.start <= p.paragraph_start < sec.end]
        wsum = sum(p.word_count for p, _ in in_sec)
        ai_val = round(sum(sc.score * p.word_count for p, sc in in_sec) / wsum, 1) if wsum and not sec.excluded_from_ai else None
        sec_conf = None
        if ai_val is not None:
            sec_conf = "low" if wsum < 300 else _level_conf([sc.confidence for _, sc in in_sec], profile.max_confidence)
        sim_words = [(p, outcome.per_passage.get(p.id)) for p in passages if sec.start <= p.paragraph_start < sec.end and p.id in outcome.per_passage]
        tot = sum(p.word_count for p, _ in sim_words)
        sim_val = round(100 * sum(c for _, c in sim_words) / tot, 1) if tot else None
        page_start = next((b.page for b in blocks[sec.start : sec.end] if b.page), None)
        page_end = next((b.page for b in reversed(blocks[sec.start : sec.end]) if b.page), None)
        db.add(
            SectionResult(
                analysis_id=a.id, order=sec.order, parent_order=sec.parent_order, kind=sec.kind, level=sec.level,
                title=sec.title or ("—" if sec.kind != "front_matter" else ""), page_start=page_start, page_end=page_end,
                word_count=sum(len(words(b.text)) for b in blocks[sec.start + (0 if sec.kind == "front_matter" else 1) : sec.end]),
                ai_likelihood=ai_val, ai_confidence=sec_conf, similarity=sim_val,
                suspicious_count=sum(1 for p, _ in flagged if sec.start <= p.paragraph_start < sec.end),
                excluded_from_ai=sec.excluded_from_ai, style_metrics=sec_metrics.get(sec.order, {}),
            )
        )

    # ---- flagged passages (only these keep their text)
    for p, sc in flagged:
        db.add(
            PassageAnalysis(
                analysis_id=a.id, section_order=p.section_order, chapter_order=p.chapter_order, page=p.page,
                paragraph_index=p.paragraph_start, paragraph_end=p.paragraph_end, text=p.text, word_count=p.word_count,
                ai_likelihood=sc.score, confidence=sc.confidence, characteristics=sc.characteristics,
                metrics={k: round(float(v), 4) for k, v in sc.metrics.items()}, provider_scores=provider_scores.get(p.id, []),
            )
        )

    # ---- similarity matches
    for m in outcome.matches[:300]:
        p = pmap[m.passage_id]
        other = pmap.get(m.other_passage_id) if m.other_passage_id is not None else None
        db.add(
            SimilarityMatch(
                analysis_id=a.id, match_type=m.match_type, provider="local", section_order=p.section_order, page=p.page,
                paragraph_index=p.paragraph_start, text=p.text[:1500], matched_text=other.text[:1500] if other else "",
                matched_page=other.page if other else m.matched_page,
                matched_paragraph_index=other.paragraph_start if other else m.matched_paragraph_index,
                matched_document_id=m.matched_document_id,
                matched_document_name=_doc_name(db, m.matched_document_id), similarity=m.similarity,
            )
        )
    for m in outcome.paraphrases:
        p, other = pmap[m.passage_id], pmap[m.other_passage_id]
        db.add(
            SimilarityMatch(
                analysis_id=a.id, match_type="paraphrase", provider="local", section_order=p.section_order, page=p.page,
                paragraph_index=p.paragraph_start, text=p.text[:1500], matched_text=other.text[:1500], matched_page=other.page,
                matched_paragraph_index=other.paragraph_start, similarity=m.similarity,
            )
        )
    for m in ext_matches:
        db.add(m)

    # ---- document-level
    doc_ai = round(sum(sc.score * p.word_count for p, sc in scored) / total_scored_words, 1) if total_scored_words else None
    if doc_ai is None:
        doc_conf = "low"
    else:
        share_conf = sum(1 for _, sc in scored if sc.confidence != "low") / len(scored)
        extremity = abs(doc_ai - 50)
        if total_scored_words >= 3000 and extremity >= 20 and share_conf >= 0.6:
            level = "high"
        elif total_scored_words >= 800 and extremity >= 8 and share_conf >= 0.3:
            level = "medium"
        else:
            level = "low"
        cap = profile.max_confidence
        if prep.doc.ocr_used and cap == "high":
            cap = "medium"
        if a.depth == "quick" and cap == "high":
            cap = "medium"
        doc_conf = CONF[min(CONF.index(level), CONF.index(cap))]

    bins = [0] * 10
    for _, sc in scored:
        bins[min(9, int(sc.score // 10))] += 1
    n_blocks = max(1, len(blocks))
    positions = [
        {"pos": round(p.paragraph_start / n_blocks, 4), "score": sc.score, "flagged": sc.score >= threshold, "page": p.page, "chapter_order": p.chapter_order}
        for p, sc in sorted(scored, key=lambda x: x[0].paragraph_start)
    ]
    overall = outcome.overall
    db.add(
        AnalysisResult(
            analysis_id=a.id,
            ai_likelihood=doc_ai,
            ai_confidence=doc_conf,
            ai_basis="local_linguistic",
            passages_analyzed=len(scored),
            passages_flagged=len(flagged),
            flagged_word_share=round(100 * sum(p.word_count for p, _ in flagged) / total_scored_words, 1) if total_scored_words else 0.0,
            similarity_overall=overall,
            similarity_internal=outcome.internal_coverage,
            similarity_corpus=outcome.corpus_coverage,
            similarity_external=external_cov,
            similarity_scope=sim_scope,
            providers=providers_used,
            provider_comparison=comparison,
            score_distribution=[{"range": f"{i * 10}–{i * 10 + 10}", "count": c} for i, c in enumerate(bins)],
            passage_positions=positions[:3000],
            style=style,
            academic=academic,
            paraphrase={"count": len(outcome.paraphrases)},
            repeated_phrases=outcome.repeated_phrases,
            metrics={
                "passages_total": len(passages),
                "passages_excluded": sum(1 for p in passages if p.excluded_from_ai),
                "language": prep.language,
                "language_note": profile.reliability_note,
                "threshold": threshold,
                "depth": a.depth,
                "ocr_used": prep.doc.ocr_used,
                "pages_estimated": prep.doc.pages_estimated,
                "method_version": ai.METHOD_VERSION,
            },
            methodology_version=ai.METHOD_VERSION,
        )
    )


def _doc_name(db: Session, doc_id: str | None) -> str | None:
    if not doc_id:
        return None
    d = db.get(Document, doc_id)
    return d.original_filename if d else None
