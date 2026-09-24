"""Common pieces for harvesters that fill the reference corpus from open sources."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.providers.resilience import RateLimiter

log = logging.getLogger(__name__)
UA = "AcademicAnalyzer/1.0 (reference-corpus harvester; mailto configured by operator)"


@dataclass
class HarvestItem:
    source_type: str
    title: str
    text: str  # full text when available, otherwise title + abstract
    authors: str = ""
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    fulltext: bool = False
    pdf_url: str | None = None
    extra: dict = field(default_factory=dict)


class Harvester:
    source_type = "base"

    def __init__(self, client: httpx.Client | None = None):
        s = get_settings()
        self.client = client or httpx.Client(timeout=40, headers={"User-Agent": UA}, follow_redirects=True)
        self.limiter = RateLimiter(max(1, int(s.HARVEST_RPS * 60)))

    def get(self, url: str, **kw) -> httpx.Response:
        self.limiter.wait()
        r = self.client.get(url, **kw)
        r.raise_for_status()
        return r

    def harvest(self, target: str, limit: int) -> Iterator[HarvestItem]:  # pragma: no cover - interface
        raise NotImplementedError


def reconstruct_abstract(inverted: dict | None) -> str:
    """OpenAlex stores abstracts as an inverted index {word: [positions]}."""
    if not inverted:
        return ""
    pos: dict[int, str] = {}
    for word, idxs in inverted.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def strip_jats(text: str | None) -> str:
    if not text:
        return ""
    import re

    return re.sub(r"<[^>]+>", " ", text).strip()
