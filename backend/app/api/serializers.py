"""Response shaping. Adds localized labels/explanations to stored codes."""
from __future__ import annotations

from app.core.i18n import DISCLAIMER, ESTIMATE_NOTE, explain_characteristics, issue_text, t
from app.models import Analysis, Document, PassageAnalysis, SectionResult, SimilarityMatch


def version_out(v) -> dict | None:
    if v is None:
        return None
    return {
        "id": v.id, "version_no": v.version_no, "page_count": v.page_count, "pages_estimated": v.pages_estimated,
        "word_count": v.word_count, "char_count": v.char_count, "paragraph_count": v.paragraph_count,
        "language": v.language, "language_confidence": v.language_confidence, "language_distribution": v.language_distribution,
        "is_scanned": v.is_scanned, "ocr_used": v.ocr_used, "structure_source": v.structure_source, "warnings": v.warnings,
    }


def document_out(d: Document) -> dict:
    latest = d.analyses[-1] if d.analyses else None
    return {
        "id": d.id, "original_filename": d.original_filename, "file_type": d.file_type, "doc_type": d.doc_type,
        "size_bytes": d.size_bytes, "created_at": d.created_at, "file_available": bool(d.storage_key),
        "file_deleted_at": d.file_deleted_at, "keep_for_similarity": d.keep_for_similarity,
        "version": version_out(d.versions[-1] if d.versions else None),
        "latest_analysis": analysis_summary(latest) if latest else None,
        "analyses_count": len(d.analyses),
    }


def analysis_summary(a: Analysis) -> dict:
    r = a.result
    v = a.version
    return {
        "id": a.id, "document_id": a.document_id, "document_name": a.document.original_filename if a.document else None,
        "doc_type": a.document.doc_type if a.document else None,
        "depth": a.depth, "status": a.status, "progress": a.progress, "stage": a.stage, "message": a.message, "error": a.error,
        "created_at": a.created_at, "finished_at": a.finished_at, "duration_seconds": a.duration_seconds,
        "language": v.language if v else None, "word_count": v.word_count if v else None, "page_count": v.page_count if v else None,
        "ai_likelihood": r.ai_likelihood if r else None, "ai_confidence": r.ai_confidence if r else None,
        "similarity_overall": r.similarity_overall if r else None,
    }


def analysis_detail(a: Analysis, lang: str = "uz") -> dict:
    out = analysis_summary(a)
    out["version"] = version_out(a.version)
    out["file_available"] = bool(a.document.storage_key)
    r = a.result
    if r is None:
        out["result"] = None
        return out
    comp = dict(r.provider_comparison or {})
    comp["summary_text"] = t(f"compare.{comp.get('summary', 'single_method')}", lang)
    academic = dict(r.academic or {})
    academic["issues"] = [dict(i, text=issue_text(i, lang), severity_label=t(f"sev.{i['severity']}", lang)) for i in academic.get("issues", [])]
    for c in academic.get("components", []):
        c["label"] = t(f"kind.{c['kind']}", lang)
    out["result"] = {
        "ai": {
            "likelihood": r.ai_likelihood, "confidence": r.ai_confidence, "confidence_label": t(f"conf.{r.ai_confidence}", lang),
            "basis": r.ai_basis, "basis_text": t("compare.single_method", lang), "note": ESTIMATE_NOTE.get(lang, ESTIMATE_NOTE["en"]),
            "passages_analyzed": r.passages_analyzed, "passages_flagged": r.passages_flagged, "flagged_word_share": r.flagged_word_share,
            "threshold": (r.metrics or {}).get("threshold"), "language_note": (r.metrics or {}).get("language_note"),
        },
        "similarity": {
            "overall": r.similarity_overall, "internal": r.similarity_internal, "corpus": r.similarity_corpus,
            "external": r.similarity_external, "scope": r.similarity_scope, "scope_text": t(f"scope.{r.similarity_scope}", lang),
            "external_configured": r.similarity_scope.startswith("local_and_external") or r.similarity_external is not None,
            "paraphrase_candidates": (r.paraphrase or {}).get("count", 0),
        },
        "providers": [dict(p, status_label=t(f"prov.{p.get('status')}", lang)) for p in (r.providers or [])],
        "provider_comparison": comp,
        "score_distribution": r.score_distribution,
        "passage_positions": r.passage_positions,
        "style": r.style,
        "academic": academic,
        "repeated_phrases": r.repeated_phrases,
        "metrics": r.metrics,
        "methodology_version": r.methodology_version,
        "disclaimer": DISCLAIMER.get(lang, DISCLAIMER["en"]),
    }
    return out


def section_out(s: SectionResult, lang: str = "uz") -> dict:
    return {
        "order": s.order, "parent_order": s.parent_order, "kind": s.kind, "kind_label": t(f"kind.{s.kind}", lang),
        "level": s.level, "title": s.title, "page_start": s.page_start, "page_end": s.page_end, "word_count": s.word_count,
        "ai_likelihood": s.ai_likelihood, "ai_confidence": s.ai_confidence,
        "ai_confidence_label": t(f"conf.{s.ai_confidence}", lang) if s.ai_confidence else None,
        "similarity": s.similarity, "suspicious_count": s.suspicious_count, "excluded_from_ai": s.excluded_from_ai,
    }


def passage_out(p: PassageAnalysis, sections: dict[int, SectionResult], lang: str = "uz") -> dict:
    items, explanation = explain_characteristics(p.characteristics or [], lang, p.confidence)
    sec = sections.get(p.section_order) if p.section_order is not None else None
    ch = sections.get(p.chapter_order) if p.chapter_order is not None else None
    return {
        "id": p.id, "page": p.page, "paragraph_number": p.paragraph_index + 1, "paragraph_end_number": p.paragraph_end + 1,
        "section_order": p.section_order, "section_title": sec.title if sec else None,
        "chapter_order": p.chapter_order, "chapter_title": ch.title if ch else None,
        "text": p.text, "word_count": p.word_count, "ai_likelihood": p.ai_likelihood,
        "confidence": p.confidence, "confidence_label": t(f"conf.{p.confidence}", lang),
        "characteristics": items, "explanation": explanation,
        "provider_scores": p.provider_scores or [],
    }


def match_out(m: SimilarityMatch, sections: dict[int, SectionResult], lang: str = "uz") -> dict:
    sec = sections.get(m.section_order) if m.section_order is not None else None
    return {
        "id": m.id, "match_type": m.match_type, "match_type_label": t(f"match.{m.match_type}", lang), "provider": m.provider,
        "section_title": sec.title if sec else None, "page": m.page,
        "paragraph_number": m.paragraph_index + 1 if m.paragraph_index is not None else None,
        "text": m.text, "matched_text": m.matched_text, "matched_page": m.matched_page,
        "matched_paragraph_number": m.matched_paragraph_index + 1 if m.matched_paragraph_index is not None else None,
        "matched_document_id": m.matched_document_id, "matched_document_name": m.matched_document_name,
        "source_title": m.source_title, "source_url": m.source_url, "similarity": round(m.similarity * 100, 1),
    }
