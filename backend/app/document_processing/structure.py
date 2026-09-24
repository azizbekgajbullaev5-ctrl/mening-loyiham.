"""Academic document structure detection (chapters, sections, standard parts).

Output is a flat list of *headings*; ``build_sections`` turns it into a
section tree with paragraph ranges. Users can replace the heading list
manually (see API ``PUT /documents/{id}/structure``).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from app.analyzers.languages.registry import PROFILES
from app.analyzers.text_utils import normalize, words
from app.document_processing.types import Block

SECTION_KINDS = (
    "title", "toc", "abstract", "keywords", "introduction", "literature_review", "methodology", "results",
    "discussion", "conclusion", "references", "appendix", "chapter", "section", "subsection", "heading",
    "front_matter",
)
# Parts not scored for AI-likelihood (lists, references, metadata).
AI_EXCLUDED_KINDS = {"title", "toc", "keywords", "references", "appendix", "front_matter"}
SIMILARITY_EXCLUDED_KINDS = {"toc", "references", "title", "keywords"}
TOP_LEVEL_KINDS = {
    "title", "toc", "abstract", "keywords", "introduction", "literature_review", "methodology", "results",
    "discussion", "conclusion", "references", "appendix", "chapter",
}

_SUBSECTION_RE = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\.?\s+(\S.*)$")
_SECTION_RE = re.compile(r"^\s*(\d+)\.(\d+)\.?\s+([^\d\s].*)$")
_PARAGRAPH_SECTION_RE = re.compile(r"^\s*(\d+)\s*[-–]\s*(?:§|paragraf|параграф)\b|^\s*§\s*(\d+)\.(\d+)", re.I)
_TOC_LEADER_RE = re.compile(r"(\.{3,}|…{2,}|_{3,}|\t)\s*\d{1,4}\s*$")
_TOC_TRAILING_NUM_RE = re.compile(r"\s\d{1,4}$")
_NUMBER_PREFIX = re.compile(r"^\s*(?:[IVXLC]+|\d+(?:\.\d+)*)[.)]?\s+", re.I)


@dataclass
class Heading:
    paragraph_index: int
    kind: str
    level: int
    title: str
    number: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _keyword_kind(text: str) -> str | None:
    t = normalize(text).lower().strip()
    t = _NUMBER_PREFIX.sub("", t).strip(" :.-–—")
    t = re.sub(r"\s+", " ", t)
    for prof in PROFILES.values():
        for kind, kws in prof.section_keywords.items():
            for kw in kws:
                if t == kw:
                    return kind
                # "Kalit so'zlar: ...", "Keywords: ..." carry content inline
                if kind == "keywords" and t.startswith(kw):
                    return kind
                if t.startswith(kw) and len(t) <= len(kw) + 45 and not t.endswith("."):
                    return kind
    return None


def _is_toc_entry(text: str) -> bool:
    if _TOC_LEADER_RE.search(text):  # dotted leader / tab + page number
        return True
    return bool(_TOC_TRAILING_NUM_RE.search(text)) and len(words(text)) >= 2


def _plausible_numbered_heading(rest: str, text: str, n_words: int) -> bool:
    """'1.2. Title' is a heading; '2.5 million students were ...' is not."""
    if not rest[:1].isupper():
        return False
    return (not text.rstrip().endswith(".") and n_words <= 25) or n_words <= 12


def detect_headings(blocks: list[Block], language: str) -> list[Heading]:
    profiles = [PROFILES[language]] if language in PROFILES else []
    profiles += [p for code, p in PROFILES.items() if code != language]
    headings: list[Heading] = []
    in_toc = False

    for b in blocks:
        if b.kind == "table":
            continue
        text = b.text.strip()
        n_words = len(words(text))
        if not text or n_words == 0:
            continue
        short = len(text) <= 200 and n_words <= 25
        styled = b.kind == "heading"

        kind = _keyword_kind(text) if (short or text.lower().startswith(("kalit", "keyword", "ключев", "tayanch"))) else None
        if kind == "toc":
            in_toc = True
            headings.append(Heading(b.index, "toc", 1, text[:300]))
            continue
        if in_toc:
            # TOC entries end with page numbers; the TOC ends at the first line that does not.
            if _is_toc_entry(text) or (b.style or "").lower().startswith(("toc", "оглавление")):
                continue
            in_toc = False

        if short and _is_toc_entry(text) and not styled:
            continue

        if short:
            chap = None
            for prof in profiles:
                for rx in prof.chapter_regex():
                    if rx.match(text):
                        chap = rx
                        break
                if chap:
                    break
            if chap:
                headings.append(Heading(b.index, "chapter", 1, text[:300]))
                continue
            m3 = _SUBSECTION_RE.match(text)
            if m3 and (styled or _plausible_numbered_heading(m3.group(4), text, n_words)):
                headings.append(Heading(b.index, "subsection", 3, text[:300], f"{m3.group(1)}.{m3.group(2)}.{m3.group(3)}"))
                continue
            m2 = _SECTION_RE.match(text)
            if m2 and (styled or _plausible_numbered_heading(m2.group(3), text, n_words)):
                headings.append(Heading(b.index, "section", 2, text[:300], f"{m2.group(1)}.{m2.group(2)}"))
                continue
            mp = _PARAGRAPH_SECTION_RE.match(text)
            if mp:
                headings.append(Heading(b.index, "section", 2, text[:300]))
                continue
        if kind:
            headings.append(Heading(b.index, kind, 1, text[:300]))
            continue
        if styled and short:
            lvl = b.heading_level if b.heading_level is not None else 2
            if lvl == 0 or (not headings and b.index < 3 and (b.page in (None, 1))):
                headings.append(Heading(b.index, "title", 1, text[:300]))
            elif lvl == 1:
                headings.append(Heading(b.index, "heading", 1, text[:300]))
            else:
                headings.append(Heading(b.index, "subsection" if lvl >= 3 else "section", min(3, lvl), text[:300]))

    # A title is the first styled/short heading-like block on the first page before any heading.
    if not any(h.kind == "title" for h in headings):
        first_heading = headings[0].paragraph_index if headings else len(blocks)
        for b in blocks[: min(first_heading, 8)]:
            if b.kind != "table" and 2 <= len(words(b.text)) <= 30 and not b.text.endswith("."):
                if b.kind == "heading" or b.text.isupper() or b.index == 0:
                    headings.insert(0, Heading(b.index, "title", 1, b.text[:300]))
                    break
    return _dedupe(headings)


def _dedupe(headings: list[Heading]) -> list[Heading]:
    seen: set[int] = set()
    out = []
    for h in sorted(headings, key=lambda h: h.paragraph_index):
        if h.paragraph_index in seen:
            continue
        seen.add(h.paragraph_index)
        out.append(h)
    return out


@dataclass
class Section:
    order: int
    kind: str
    level: int
    title: str
    start: int  # heading paragraph index (inclusive)
    end: int  # exclusive, includes child sections
    own_end: int  # exclusive, up to the next heading of any level
    parent_order: int | None
    chapter_order: int | None  # top-level ancestor

    @property
    def excluded_from_ai(self) -> bool:
        return self.kind in AI_EXCLUDED_KINDS


def build_sections(headings: list[Heading | dict], n_blocks: int) -> list[Section]:
    hs = [h if isinstance(h, Heading) else Heading(**{k: h[k] for k in ("paragraph_index", "kind", "level", "title")}, number=h.get("number")) for h in headings]
    hs = sorted(hs, key=lambda h: h.paragraph_index)
    sections: list[Section] = []
    if not hs or hs[0].paragraph_index > 0:
        first = hs[0].paragraph_index if hs else n_blocks
        sections.append(Section(0, "front_matter", 1, "", 0, first, first, None, 0))
    for i, h in enumerate(hs):
        nxt_any = hs[i + 1].paragraph_index if i + 1 < len(hs) else n_blocks
        end = n_blocks
        for h2 in hs[i + 1 :]:
            if h2.level <= h.level:
                end = h2.paragraph_index
                break
        sections.append(Section(len(sections), h.kind, h.level, h.title, h.paragraph_index, end, nxt_any, None, None))
    # parents: nearest previous section with lower level whose range contains this one
    stack: list[Section] = []
    for s in sections:
        while stack and not (stack[-1].level < s.level and stack[-1].start <= s.start < stack[-1].end):
            stack.pop()
        s.parent_order = stack[-1].order if stack else None
        s.chapter_order = stack[0].order if stack else s.order
        stack.append(s)
    return sections


def section_for_block(sections: list[Section]) -> dict[int, Section]:
    """Map each block index -> its own (leaf) section."""
    out: dict[int, Section] = {}
    for s in sections:
        for idx in range(s.start, s.own_end):
            out[idx] = s
    return out
