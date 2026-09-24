"""Academic-writing quality indicators.

Purely linguistic/formal checks. This module does NOT assess the scientific
validity or originality of research.
"""
from __future__ import annotations

import re
from collections import Counter

from app.analyzers.languages.base import LanguageProfile
from app.analyzers.text_utils import APOSTROPHES, mattr, normalize, split_sentences, words, words_lower
from app.document_processing.structure import Section
from app.document_processing.types import Block

DISSERTATION_TYPES = {"phd_dissertation", "masters_dissertation"}
ARTICLE_TYPES = {"article", "conference_paper"}
EXPECTED_COMPONENTS = {
    "dissertation": ["abstract", "introduction", "literature_review", "methodology", "results", "discussion", "conclusion", "references"],
    "article": ["abstract", "keywords", "introduction", "methodology", "results", "conclusion", "references"],
    "other": ["introduction", "conclusion", "references"],
}
_NUMERIC_CIT = re.compile(r"\[\s*(\d+(?:\s*[,;–-]\s*\d+)*)(?:\s*[,;]\s*[^\]]{0,20})?\]")
_AUTHOR_YEAR = re.compile(r"\(([A-ZА-ЯЁ][^()]{1,60}?),?\s((?:19|20)\d{2})[a-z]?(?:[,;:][^()]{0,20})?\)")
_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")
_ABBR = re.compile(r"\b[A-ZА-ЯЁ]{2,6}\b(?!['’ʻ])")
_REF_NUM = re.compile(r"^\s*\[?(\d{1,4})[\].)]\s*")
_COMMON_ABBR = {"SPSS", "PDF", "URL", "DOI", "ISBN", "ISSN", "OAK", "СССР", "США", "ООН", "IT", "AI", "UK", "USA", "EU", "UN", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XX", "XXI", "BOB", "ГЛАВА"}


def _expand_numeric(spec: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r"[,;]", spec):
        part = part.strip()
        m = re.match(r"(\d+)\s*[–-]\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < b - a < 50:
                out.extend(range(a, b + 1))
        elif part.isdigit():
            out.append(int(part))
    return out


def analyze_academic(
    blocks: list[Block], sections: list[Section], profile: LanguageProfile, doc_type: str
) -> dict:
    issues: list[dict] = []
    text_blocks = [b for b in blocks if b.kind != "table"]
    ref_sections = [s for s in sections if s.kind == "references"]
    ref_block_idx: set[int] = set()
    for s in ref_sections:
        ref_block_idx.update(range(s.start + 1, s.end))
    heading_idx = {s.start for s in sections if s.kind != "front_matter"}
    body_blocks = [b for b in text_blocks if b.index not in ref_block_idx and b.index not in heading_idx]
    body_text = "\n".join(b.text for b in body_blocks)

    # ---------------- sentence clarity / vocabulary
    sents = split_sentences(body_text, profile.abbreviations)
    lens = [len(words(s)) for s in sents if len(words(s)) >= 3]
    long_share = sum(1 for n in lens if n > profile.long_sentence_words) / len(lens) if lens else 0.0
    toks = words_lower(body_text)
    acad = sum(1 for t in toks if any(t.startswith(a) for a in profile.academic_words)) if profile.academic_words else 0
    metrics = {
        "sentences": len(lens),
        "avg_sentence_length": round(sum(lens) / len(lens), 1) if lens else 0.0,
        "long_sentence_share": round(long_share * 100, 1),
        "academic_vocabulary_share": round(acad / len(toks) * 100, 2) if toks else 0.0,
        "lexical_diversity_mattr": round(mattr(toks), 3),
        "cohesion": round(_cohesion(sents, profile), 3),
    }
    if long_share > 0.25:
        issues.append({"code": "many_long_sentences", "severity": "warning", "params": {"share": metrics["long_sentence_share"], "limit": profile.long_sentence_words}})
    if lens and metrics["cohesion"] < 0.015 and len(lens) > 30:
        issues.append({"code": "low_cohesion", "severity": "info", "params": {"value": metrics["cohesion"]}})

    # ---------------- components
    family = "dissertation" if doc_type in DISSERTATION_TYPES else "article" if doc_type in ARTICLE_TYPES else "other"
    present = Counter(s.kind for s in sections)
    has_chapters = present.get("chapter", 0) > 0
    components = []
    for kind in EXPECTED_COMPONENTS[family]:
        wc = sum(_words_in(blocks, s) for s in sections if s.kind == kind)
        is_present = present.get(kind, 0) > 0
        components.append({"kind": kind, "present": is_present, "word_count": wc})
        # Methodology/results/discussion are often chapters with custom titles in dissertations.
        if not is_present and not (family == "dissertation" and has_chapters and kind in {"literature_review", "methodology", "results", "discussion"}):
            issues.append({"code": "missing_component", "severity": "warning", "params": {"kind": kind}})

    # ---------------- citations & references
    references = [b.text for b in text_blocks if b.index in ref_block_idx]
    cited_numbers: list[int] = []
    for m in _NUMERIC_CIT.finditer(body_text):
        cited_numbers.extend(_expand_numeric(m.group(1)))
    author_year = _AUTHOR_YEAR.findall(body_text)
    style = "numeric" if cited_numbers and not author_year else "author_year" if author_year and not cited_numbers else "mixed" if cited_numbers and author_year else "none"
    ref_numbers = []
    for i, r in enumerate(references, start=1):
        m = _REF_NUM.match(r)
        ref_numbers.append(int(m.group(1)) if m else i)
    n_refs = len(references)
    cited_set = set(cited_numbers)
    missing_refs = sorted(n for n in cited_set if n_refs and n > max(ref_numbers or [0]))
    uncited = sorted(set(ref_numbers) - cited_set) if style == "numeric" else []
    citations = {
        "style": style,
        "in_text_count": len(cited_numbers) + len(author_year),
        "numeric_citations": len(cited_numbers),
        "author_year_citations": len(author_year),
        "cited_reference_numbers": sorted(cited_set)[:500],
        "missing_references": missing_refs,
        "uncited_references": uncited[:200],
    }
    if style == "mixed":
        issues.append({"code": "mixed_citation_style", "severity": "warning", "params": {}})
    if missing_refs:
        issues.append({"code": "citation_without_reference", "severity": "warning", "params": {"numbers": missing_refs[:20]}})
    if uncited:
        issues.append({"code": "uncited_references", "severity": "info", "params": {"count": len(uncited), "numbers": uncited[:20]}})
    if not ref_sections:
        issues.append({"code": "no_reference_list", "severity": "warning", "params": {}})
    if ref_sections and not citations["in_text_count"]:
        issues.append({"code": "no_in_text_citations", "severity": "warning", "params": {}})

    # sections without citations where they are expected
    no_cite_sections = []
    for s in sections:
        if s.kind in {"literature_review", "chapter", "section", "introduction"}:
            sec_text = " ".join(b.text for b in text_blocks if s.start < b.index < s.own_end)
            if len(words(sec_text)) >= 250 and not (_NUMERIC_CIT.search(sec_text) or _AUTHOR_YEAR.search(sec_text)):
                no_cite_sections.append({"order": s.order, "title": s.title})
    citations["sections_without_citations"] = no_cite_sections
    if no_cite_sections:
        issues.append({"code": "sections_without_citations", "severity": "info", "params": {"count": len(no_cite_sections)}})

    years = [int(m) for r in references for m in _YEAR.findall(r)]
    ref_years = []
    missing_year = []
    for i, r in enumerate(references, start=1):
        ys = [int(y) for y in _YEAR.findall(r)]
        if ys:
            ref_years.append(max(ys))
        else:
            missing_year.append(i)
    dup = [r for r, c in Counter(re.sub(r"^\s*\[?\d+[\].)]\s*", "", normalize(x).lower()).strip() for x in references).items() if c > 1 and r]
    numbering_ok = ref_numbers == list(range(1, n_refs + 1)) if references and all(_REF_NUM.match(r) for r in references) else None
    gost = sum(1 for r in references if "//" in r or re.search(r"\s–\s", r))
    apa = sum(1 for r in references if re.search(r"\((?:19|20)\d{2}\)", r))
    ref_info = {
        "count": n_refs,
        "with_year": len(ref_years),
        "missing_year": missing_year[:50],
        "duplicates": len(dup),
        "year_min": min(ref_years) if ref_years else None,
        "year_max": max(ref_years) if ref_years else None,
        "older_than_10y_share": round(sum(1 for y in ref_years if y < max(years or [0]) - 10) / len(ref_years) * 100, 1) if ref_years else None,
        "numbering_sequential": numbering_ok,
        "format_styles": {"gost_like": gost, "apa_like": apa, "other": n_refs - gost - apa if n_refs >= gost + apa else 0},
    }
    if missing_year:
        issues.append({"code": "references_missing_year", "severity": "info", "params": {"count": len(missing_year)}})
    if dup:
        issues.append({"code": "duplicate_references", "severity": "warning", "params": {"count": len(dup)}})
    if gost and apa and min(gost, apa) >= max(2, n_refs * 0.15):
        issues.append({"code": "mixed_reference_formats", "severity": "info", "params": {"gost": gost, "apa": apa}})
    if numbering_ok is False:
        issues.append({"code": "reference_numbering", "severity": "info", "params": {}})

    # ---------------- headings
    heading_info = _heading_consistency(sections)
    for code in heading_info["issues"]:
        issues.append({"code": code["code"], "severity": "info", "params": code.get("params", {})})

    # ---------------- terminology / formatting
    raw_text = "\n".join(b.text for b in text_blocks)
    term = _terminology(raw_text, profile, "\n".join(b.text for b in body_blocks if not b.text.isupper()))
    if term["apostrophe_variants"] and len(term["apostrophe_variants"]) > 1 and profile.code == "uz":
        issues.append({"code": "mixed_apostrophes", "severity": "info", "params": {"variants": term["apostrophe_variants"]}})
    if term["spelling_variants"]:
        issues.append({"code": "term_variants", "severity": "info", "params": {"count": len(term["spelling_variants"])}})
    if term["undefined_abbreviations"]:
        issues.append({"code": "undefined_abbreviations", "severity": "info", "params": {"items": term["undefined_abbreviations"][:10]}})

    fmt = {
        "double_spaces": sum(b.text.count("  ") for b in text_blocks),
        "very_long_paragraphs": sum(1 for b in body_blocks if len(words(b.text)) > 350),
        "all_caps_paragraphs": sum(1 for b in body_blocks if len(b.text) > 80 and b.text.isupper()),
        "quote_styles": {q: raw_text.count(q) for q in ("«", "“", '"') if raw_text.count(q)},
    }
    if len(fmt["quote_styles"]) > 1:
        issues.append({"code": "mixed_quotes", "severity": "info", "params": {"styles": list(fmt["quote_styles"])}})
    if fmt["very_long_paragraphs"]:
        issues.append({"code": "very_long_paragraphs", "severity": "info", "params": {"count": fmt["very_long_paragraphs"]}})

    # ---------------- repetition & transitions
    content = [t for t in toks if t not in profile.stopwords and len(t) > 3]
    cnt = Counter(content)
    overused = [{"word": w, "count": c, "per_1000": round(c / max(1, len(toks)) * 1000, 2)} for w, c in cnt.most_common(15) if c / max(1, len(toks)) > 0.008 and c >= 8]
    sent_norm = Counter(normalize(s).lower().strip() for s in sents if len(words(s)) >= 8)
    repeated_sentences = sum(c - 1 for c in sent_norm.values() if c > 1)
    if repeated_sentences:
        issues.append({"code": "repeated_sentences", "severity": "warning", "params": {"count": repeated_sentences}})
    trans = Counter()
    for s in sents:
        low = s.lower().lstrip("\"'«“( ")
        for t in profile.transitions:
            if low.startswith(t) and (len(low) == len(t) or not low[len(t)].isalnum()):
                trans[t] += 1
                break
    trans_total = sum(trans.values())
    overused_trans = [{"marker": t, "count": c} for t, c in trans.most_common(8) if lens and c / len(lens) > 0.04 and c >= 4]
    if overused_trans:
        issues.append({"code": "overused_transitions", "severity": "info", "params": {"markers": [x["marker"] for x in overused_trans]}})

    return {
        "doc_family": family,
        "metrics": metrics,
        "components": components,
        "citations": citations,
        "references": ref_info,
        "headings": heading_info,
        "terminology": term,
        "formatting": fmt,
        "repetition": {"overused_words": overused, "repeated_sentences": repeated_sentences},
        "transitions": {"total": trans_total, "top": [{"marker": t, "count": c} for t, c in trans.most_common(10)], "overused": overused_trans},
        "issues": issues,
    }


def _words_in(blocks: list[Block], s: Section) -> int:
    return sum(len(words(b.text)) for b in blocks[s.start + 1 : s.end] if b.kind != "table")


def _cohesion(sents: list[str], profile: LanguageProfile) -> float:
    """Mean content-word overlap (Jaccard over 5-char stems) between adjacent sentences."""
    def stems(s: str) -> set[str]:
        return {w[:5] for w in words_lower(s) if w not in profile.stopwords and len(w) > 3}

    vals = []
    prev = None
    for s in sents:
        cur = stems(s)
        if prev is not None and (prev or cur):
            vals.append(len(prev & cur) / max(1, len(prev | cur)))
        prev = cur
    return sum(vals) / len(vals) if vals else 0.0


def _heading_consistency(sections: list[Section]) -> dict:
    issues = []
    nums = []
    for s in sections:
        m = re.match(r"^\s*(\d+)\.(\d+)", s.title)
        if s.kind in {"section", "subsection"} and m:
            nums.append((int(m.group(1)), int(m.group(2)), s.title))
    gaps = []
    for (a1, b1, _), (a2, b2, t2) in zip(nums, nums[1:]):
        if a2 == a1 and b2 not in (b1, b1 + 1) and b2 > b1:
            gaps.append(t2[:80])
        if a2 == a1 + 1 and b2 != 1:
            gaps.append(t2[:80])
    if gaps:
        issues.append({"code": "heading_numbering_gap", "params": {"items": gaps[:10]}})
    titled = [s.title for s in sections if s.title and s.kind not in {"front_matter", "title", "keywords"}]
    upper = sum(1 for t in titled if t.isupper())
    if titled and 0 < upper < len(titled):
        tops = [s.title for s in sections if s.level == 1 and s.title and s.kind not in {"front_matter", "title", "keywords"}]
        top_upper = sum(1 for t in tops if t.isupper())
        if tops and 0 < top_upper < len(tops):
            issues.append({"code": "heading_case_mixed", "params": {}})
    periods = sum(1 for t in titled if t.rstrip().endswith("."))
    if titled and 0 < periods < len(titled) and periods >= 2:
        issues.append({"code": "heading_trailing_period_mixed", "params": {}})
    chapters = [s for s in sections if s.kind == "chapter"]
    return {"chapter_count": len(chapters), "section_count": sum(1 for s in sections if s.kind in {"section", "subsection"}), "numbering_gaps": gaps, "issues": issues}


_APOS_RE = re.compile(r"[oOgG]([" + re.escape(APOSTROPHES + "'") + r"])")


def _terminology(text: str, profile: LanguageProfile, body_text: str = "") -> dict:
    variants = Counter(m.group(1) for m in _APOS_RE.finditer(text))
    apostrophe_variants = {repr(k)[1:-1]: v for k, v in variants.items() if v >= 3}
    norm = normalize(text)
    # hyphen/space spelling variants: "e-learning" vs "elearning" vs "e learning"
    hyph = Counter(m.lower() for m in re.findall(r"\b\w{2,}-\w{2,}\b", norm))
    spelling = []
    lower = norm.lower()
    for h, c in hyph.items():
        joined = h.replace("-", "")
        spaced = h.replace("-", " ")
        jc = len(re.findall(rf"\b{re.escape(joined)}\b", lower))
        sc = len(re.findall(rf"\b{re.escape(spaced)}\b", lower))
        if jc or sc:
            spelling.append({"forms": [h] + ([joined] if jc else []) + ([spaced] if sc else []), "counts": [c, jc, sc]})
    # abbreviations never defined in parentheses
    body = normalize(body_text or text)
    abbrs = Counter(_ABBR.findall(body))
    undefined = []
    for a, c in abbrs.items():
        if a in _COMMON_ABBR or c < 2 or re.fullmatch(r"[IVXLC]+", a):
            continue
        if not re.search(rf"\(\s*{re.escape(a)}\s*\)|{re.escape(a)}\s*[–—-]\s*\w|{re.escape(a)}\s*\(", body):
            undefined.append(a)
    return {"apostrophe_variants": apostrophe_variants, "spelling_variants": spelling[:20], "undefined_abbreviations": sorted(undefined)[:30]}
