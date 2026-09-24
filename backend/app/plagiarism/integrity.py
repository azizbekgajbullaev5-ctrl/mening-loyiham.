"""Detection of technical tricks used to defeat plagiarism checkers.

Reported separately from the originality score ("Texnik hiylalar"). The
comparison itself is already immune to them (see textnorm): homoglyphs are
normalised, invisible characters stripped, hidden text excluded.
"""
from __future__ import annotations

import re
from collections import Counter

from app.document_processing.types import Block, ExtractedDocument
from app.plagiarism.textnorm import INVISIBLE, WORD_RE, _CYR_RE, _LATIN_RE

_INVISIBLE_RE = re.compile(f"[{INVISIBLE.replace(chr(0xad), '')}]")  # soft hyphen is legitimate in PDFs/DOCX
_SPACED_RE = re.compile(r"(?<!\w)(?:[^\W\d_] ){5,}[^\W\d_](?!\w)")
_UNUSUAL_SPACES_RE = re.compile(r"[ -   　]")


def scan(doc: ExtractedDocument, blocks: list[Block] | None = None) -> dict:
    blocks = blocks if blocks is not None else doc.blocks
    homoglyph = Counter()
    homoglyph_pages: set = set()
    invisible = 0
    invisible_pages: set = set()
    spaced: list[str] = []
    unusual_spaces = 0
    total_words = 0
    for b in blocks:
        text = b.text
        for m in WORD_RE.finditer(text):
            w = m.group(0)
            total_words += 1
            if len(w) >= 3 and _LATIN_RE.search(w) and _CYR_RE.search(w):
                homoglyph[w] += 1
                homoglyph_pages.add(b.page)
        n_inv = len(_INVISIBLE_RE.findall(text))
        if n_inv:
            invisible += n_inv
            invisible_pages.add(b.page)
        for m in _SPACED_RE.finditer(text):
            spaced.append(m.group(0)[:60])
        unusual_spaces += len(_UNUSUAL_SPACES_RE.findall(text))

    items: list[dict] = []
    n_homo = sum(homoglyph.values())
    if n_homo:
        items.append({"code": "homoglyphs", "severity": "high" if n_homo >= 5 else "medium", "count": n_homo,
                      "examples": [w for w, _ in homoglyph.most_common(8)], "pages": _pages(homoglyph_pages)})
    if invisible:
        items.append({"code": "invisible_chars", "severity": "high" if invisible >= 20 else "medium", "count": invisible,
                      "pages": _pages(invisible_pages)})
    hidden = doc.hidden_fragments
    if hidden:
        chars = sum(h["chars"] for h in hidden)
        items.append({"code": "hidden_text", "severity": "high" if chars >= 200 else "medium", "count": len(hidden), "chars": chars,
                      "reasons": dict(Counter(h["reason"] for h in hidden)), "examples": [h["sample"] for h in hidden[:5]],
                      "pages": _pages({h["page"] for h in hidden})})
    if len(spaced) >= 3:
        items.append({"code": "spaced_letters", "severity": "medium", "count": len(spaced), "examples": spaced[:5]})
    if total_words and unusual_spaces > max(20, total_words * 0.05):
        items.append({"code": "unusual_spaces", "severity": "low", "count": unusual_spaces})
    return {"suspicious": any(i["severity"] in ("high", "medium") for i in items), "items": items}


def _pages(pages: set) -> list[int]:
    return sorted(p for p in pages if p is not None)[:50]
