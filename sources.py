"""Real ilmiy manbalarni qidirish va tekshirish (OpenAlex + Crossref).

Maqola/tezis faqat internetdan topilgan real manbalar asosida yozilishi uchun
dalillar to'plamini (evidence set) tayyorlaydi. Kalit (API key) talab qilmaydi.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)

OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"
_TIMEOUT = aiohttp.ClientTimeout(total=25)
_HEADERS = {"User-Agent": "OAK-maqola-bot/1.0 (mailto:support@example.uz)"}


@dataclass
class Source:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""

    def author_str(self) -> str:
        if not self.authors:
            return ""
        shown = self.authors[:3]
        s = ", ".join(shown)
        if len(self.authors) > 3:
            s += " va b."
        return s

    def gost(self) -> str:
        """GOST R 7.0.5 ga yaqin bibliografik satr."""
        parts = []
        if self.author_str():
            parts.append(self.author_str())
        title = self.title.strip().rstrip(".")
        seg = title
        if self.journal:
            seg += f" // {self.journal}"
        parts.append(seg)
        tail = []
        if self.year:
            tail.append(str(self.year))
        link = self.doi_url() or self.url
        if link:
            tail.append(link)
        line = ". ".join(p.rstrip(". ") for p in parts if p)
        if tail:
            line += ". " + ". ".join(tail)
        return line

    def doi_url(self) -> str:
        if not self.doi:
            return ""
        d = self.doi.replace("https://doi.org/", "").strip()
        return f"https://doi.org/{d}" if d else ""


def _abstract_from_inverted(inv: dict | None) -> str:
    if not inv:
        return ""
    try:
        positions: list[tuple[int, str]] = []
        for word, idxs in inv.items():
            for i in idxs:
                positions.append((i, word))
        positions.sort()
        text = " ".join(w for _, w in positions)
        return text[:900]
    except Exception:  # noqa: BLE001
        return ""


def _clean_doi(doi: str | None) -> str:
    if not doi:
        return ""
    return doi.replace("https://doi.org/", "").strip().lower()


async def _openalex(session: aiohttp.ClientSession, query: str,
                    per_page: int = 12) -> list[Source]:
    params = {
        "search": query,
        "per-page": str(per_page),
        "sort": "relevance_score:desc",
        "filter": "has_abstract:true",
    }
    out: list[Source] = []
    try:
        async with session.get(OPENALEX_URL, params=params) as resp:
            if resp.status != 200:
                logger.warning("OpenAlex %s: %s", query, resp.status)
                return out
            data = await resp.json()
    except Exception:  # noqa: BLE001
        logger.warning("OpenAlex so'rov xatosi: %s", query, exc_info=True)
        return out

    for w in data.get("results", []):
        title = (w.get("title") or "").strip()
        if not title:
            continue
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in (w.get("authorships") or [])
            if a.get("author", {}).get("display_name")
        ]
        journal = ""
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        if src.get("display_name"):
            journal = src["display_name"]
        out.append(
            Source(
                title=title,
                authors=authors,
                year=w.get("publication_year"),
                journal=journal,
                doi=_clean_doi(w.get("doi")),
                url=(loc.get("landing_page_url") or w.get("id") or ""),
                abstract=_abstract_from_inverted(w.get("abstract_inverted_index")),
            )
        )
    return out


async def _crossref_verify(session: aiohttp.ClientSession, doi: str) -> bool:
    """DOI Crossref'da mavjudligini tekshiradi."""
    if not doi:
        return False
    try:
        async with session.get(f"{CROSSREF_URL}/{doi}") as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False


def _dedupe(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    out: list[Source] = []
    for s in sources:
        key = (s.doi or s.title.lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _rank(sources: list[Source]) -> list[Source]:
    """So'nggi yillar va DOI borlarga ustunlik beradi."""
    now = datetime.now().year

    def score(s: Source) -> tuple:
        recent = 1 if (s.year and now - s.year <= 7) else 0
        has_doi = 1 if s.doi else 0
        has_abs = 1 if s.abstract else 0
        yr = s.year or 0
        return (recent, has_doi, has_abs, yr)

    return sorted(sources, key=score, reverse=True)


async def find_sources(topic: str, field_name: str, queries: list[str],
                       want: int = 18, verify: bool = True) -> list[Source]:
    """Bir necha tilli so'rovlar bo'yicha real manbalarni yig'adi va tanlaydi.

    queries — mavzu asosida tuzilgan qidiruv so'rovlari (uz/ru/en).
    """
    all_q = [q for q in queries if q and q.strip()]
    if not all_q:
        all_q = [f"{topic} {field_name}".strip()]

    async with aiohttp.ClientSession(timeout=_TIMEOUT, headers=_HEADERS) as session:
        results = await asyncio.gather(
            *[_openalex(session, q) for q in all_q[:4]], return_exceptions=True
        )
        collected: list[Source] = []
        for r in results:
            if isinstance(r, list):
                collected.extend(r)

        collected = _rank(_dedupe(collected))

        # DOI larni Crossref orqali tekshirish (yuqori o'rindagilar)
        if verify:
            top = collected[: want + 8]
            checks = await asyncio.gather(
                *[_crossref_verify(session, s.doi) for s in top],
                return_exceptions=True,
            )
            verified: list[Source] = []
            for s, ok in zip(top, checks):
                # DOI bo'lsa va tasdiqlansa — olamiz; DOI yo'q bo'lsa ham (URL bilan)
                if not s.doi or ok is True:
                    verified.append(s)
            # Tasdiqlanganlar yetarli bo'lmasa, qolganlarни ham qo'shamiz
            rest = [s for s in collected if s not in verified]
            collected = verified + rest

    return collected[:want]


def build_evidence(sources: list[Source]) -> str:
    """Modelga beriladigan raqamlangan dalillar to'plami matni."""
    lines = []
    for i, s in enumerate(sources, 1):
        meta = s.gost()
        abs = (s.abstract or "").strip()
        if abs:
            abs = " | Annotatsiya: " + abs[:400]
        lines.append(f"[{i}] {meta}{abs}")
    return "\n".join(lines)
