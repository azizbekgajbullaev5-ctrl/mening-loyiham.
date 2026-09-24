from __future__ import annotations

from dataclasses import dataclass, field

WORDS_PER_PAGE_ESTIMATE = 280


@dataclass
class Block:
    index: int
    text: str
    kind: str = "paragraph"  # paragraph | heading | table | list
    page: int | None = None
    heading_level: int | None = None  # from DOCX style / PDF font size
    style: str | None = None
    is_ocr: bool = False


@dataclass
class ExtractedDocument:
    file_type: str
    blocks: list[Block]
    page_count: int
    pages_estimated: bool = False
    is_scanned: bool = False
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def text_blocks(self) -> list[Block]:
        return [b for b in self.blocks if b.text.strip()]


class ExtractionError(Exception):
    """Raised when a file cannot be parsed. ``code`` is a stable machine code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
