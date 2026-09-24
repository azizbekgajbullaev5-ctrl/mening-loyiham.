"""Split sections into analysis passages (chunks) with page/paragraph provenance."""
from __future__ import annotations

from dataclasses import dataclass

from app.analyzers.text_utils import sha256_text, split_sentences, words
from app.document_processing.structure import Section, section_for_block
from app.document_processing.types import Block

MIN_PASSAGE_WORDS = 120
TARGET_PASSAGE_WORDS = 220
MAX_PASSAGE_WORDS = 380


@dataclass
class Passage:
    id: int
    section_order: int
    chapter_order: int | None
    paragraph_start: int
    paragraph_end: int
    page: int | None
    text: str
    word_count: int
    hash: str
    excluded_from_ai: bool
    is_ocr: bool = False


def _split_long(text: str, abbreviations: tuple[str, ...]) -> list[str]:
    sents = split_sentences(text, abbreviations)
    chunks, cur, n = [], [], 0
    for s in sents:
        w = len(words(s))
        if cur and n + w > TARGET_PASSAGE_WORDS:
            chunks.append(" ".join(cur))
            cur, n = [], 0
        cur.append(s)
        n += w
    if cur:
        if chunks and n < MIN_PASSAGE_WORDS // 2:
            chunks[-1] += " " + " ".join(cur)
        else:
            chunks.append(" ".join(cur))
    return chunks or [text]


def segment(blocks: list[Block], sections: list[Section], abbreviations: tuple[str, ...] = ()) -> list[Passage]:
    owner = section_for_block(sections)
    heading_idx = {s.start for s in sections if s.kind != "front_matter"}
    passages: list[Passage] = []
    buf: list[Block] = []
    buf_section: Section | None = None

    def flush() -> None:
        nonlocal buf
        if not buf or buf_section is None:
            buf = []
            return
        text = " ".join(b.text for b in buf)
        passages.append(_make(len(passages), buf_section, buf[0].index, buf[-1].index, buf[0].page, text, any(b.is_ocr for b in buf)))
        buf = []

    for b in blocks:
        if b.kind == "table" or b.index in heading_idx or not b.text.strip():
            continue
        sec = owner.get(b.index)
        if sec is None:
            continue
        if sec is not buf_section:
            flush()
            buf_section = sec
        n = len(words(b.text))
        if n > MAX_PASSAGE_WORDS:
            flush()
            for chunk in _split_long(b.text, abbreviations):
                passages.append(_make(len(passages), sec, b.index, b.index, b.page, chunk, b.is_ocr))
            continue
        buf.append(b)
        if sum(len(words(x.text)) for x in buf) >= MIN_PASSAGE_WORDS:
            flush()
    flush()
    # merge a too-short trailing passage into its predecessor within the same section
    merged: list[Passage] = []
    for p in passages:
        prev = merged[-1] if merged else None
        if prev and p.word_count < MIN_PASSAGE_WORDS // 2 and prev.section_order == p.section_order and prev.word_count + p.word_count <= MAX_PASSAGE_WORDS:
            merged[-1] = _make(prev.id, _SectionLike(prev), prev.paragraph_start, p.paragraph_end, prev.page, prev.text + " " + p.text, prev.is_ocr or p.is_ocr)
        else:
            merged.append(p)
    for i, p in enumerate(merged):
        p.id = i
    return merged


class _SectionLike:
    def __init__(self, p: Passage):
        self.order = p.section_order
        self.chapter_order = p.chapter_order
        self.excluded_from_ai = p.excluded_from_ai


def _make(pid: int, sec, start: int, end: int, page: int | None, text: str, is_ocr: bool) -> Passage:
    return Passage(
        id=pid,
        section_order=sec.order,
        chapter_order=sec.chapter_order,
        paragraph_start=start,
        paragraph_end=end,
        page=page,
        text=text,
        word_count=len(words(text)),
        hash=sha256_text(text),
        excluded_from_ai=sec.excluded_from_ai,
        is_ocr=is_ocr,
    )
