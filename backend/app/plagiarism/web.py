"""Internet check: Brave Search for the most distinctive sentences, then fetch & compare pages.

Cost control: the number of queries is estimated and shown *before* the check
(the user confirms), sentences already matched in the reference corpus are
not searched, page fingerprints are cached, and every run is capped by
WEB_MAX_QUERIES. Fetching is restricted to public http(s) hosts (no private /
loopback addresses), honours robots.txt and a size limit.
"""
from __future__ import annotations

import hashlib
import io
import ipaddress
import logging
import math
import re
import socket
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyzers.text_utils import split_sentences
from app.core.config import get_settings
from app.models import WebPageCache
from app.plagiarism.fingerprint import shingles
from app.plagiarism.matcher import TokenStream, WebSource
from app.plagiarism.textnorm import canonical_stopwords, canonical_words
from app.providers.resilience import RateLimiter

log = logging.getLogger(__name__)
USER_AGENT = "AcademicAnalyzer/1.0 (academic plagiarism check; respects robots.txt)"
_CITATION_RE = re.compile(r"\[\s*\d|\((?:[^()]{0,60})(?:19|20)\d{2}")


# ---------------------------------------------------------------- estimate
def planned_queries(words: int) -> int:
    s = get_settings()
    if words <= 0:
        return 0
    return int(min(s.WEB_MAX_QUERIES, max(3, math.ceil(words / s.WEB_WORDS_PER_QUERY))))


def estimate(words: int) -> dict:
    s = get_settings()
    q = planned_queries(words)
    return {
        "words": words,
        "queries": q,
        "max_pages": q * s.WEB_RESULTS_PER_QUERY,
        "price_per_1000_usd": s.BRAVE_PRICE_PER_1000_USD,
        "cost_usd": round(q * s.BRAVE_PRICE_PER_1000_USD / 1000.0, 4),
        "configured": bool(s.BRAVE_API_KEY.get_secret_value()),
        "note": "Upper bound: sentences already found in the reference corpus are not searched.",
    }


def quick_word_count(file_type: str, data: bytes) -> int:
    """Fast word count for the cost estimate (no OCR)."""
    try:
        if file_type == "pdf":
            import pymupdf

            pdf = pymupdf.open(stream=data, filetype="pdf")
            words = sum(len(p.get_text("text").split()) for p in pdf)
            return words if words > pdf.page_count * 20 else pdf.page_count * 250  # scanned: estimate
        if file_type == "docx":
            import docx

            d = docx.Document(io.BytesIO(data))
            return sum(len(p.text.split()) for p in d.paragraphs)
        from app.document_processing.extractors import decode_text

        return len(decode_text(data).split())
    except Exception:  # noqa: BLE001
        return 0


# ---------------------------------------------------------------- query selection
@dataclass
class Query:
    text: str
    token_start: int
    token_end: int


def select_queries(stream: TokenStream, covered: np.ndarray, n: int, abbreviations: tuple[str, ...] = ()) -> list[Query]:
    """Pick up to n distinctive sentences spread over the document."""
    if n <= 0 or not stream.canon:
        return []
    stop = canonical_stopwords()
    freq: dict[str, int] = {}
    for t in stream.canon:
        freq[t] = freq.get(t, 0) + 1
    total = len(stream.canon)
    by_block: dict[int, list[tuple[int, int]]] = {}
    for i, (b, st) in enumerate(zip(stream.block, stream.start)):
        by_block.setdefault(b, []).append((st, i))
    cands: list[tuple[float, int, int, str]] = []
    for block_idx, disp in stream.displays.items():
        pos = 0
        for sent in split_sentences(disp, abbreviations):
            at = disp.find(sent[:30], pos)
            if at < 0:
                continue
            pos = at + len(sent)
            toks = [i for st, i in by_block.get(block_idx, ()) if at <= st < at + len(sent)]
            if not toks:
                continue
            a, z = min(toks), max(toks) + 1
            words = stream.canon[a:z]
            if not 10 <= len(words) <= 45 or _CITATION_RE.search(sent) or stream.quoted[a:z].any():
                continue
            if covered[a:z].mean() > 0.5:  # already found in the corpus: don't pay for a web query
                continue
            content = [w for w in words if w not in stop and len(w) > 3]
            if len(content) < 0.5 * len(words):
                continue
            rarity = sum(math.log(total / freq[w]) for w in content) / len(content)
            cands.append((rarity, a, z, sent))
    if not cands:
        return []
    cands.sort(key=lambda c: c[1])
    buckets = max(1, min(n, len(cands)))
    size = len(cands) / buckets
    chosen = []
    for k in range(buckets):
        group = cands[int(k * size) : int((k + 1) * size)] or cands[-1:]
        best = max(group, key=lambda c: c[0])
        chosen.append(best)
    out = []
    for _, a, z, sent in chosen[:n]:
        words = stream.words[a:z]
        mid = max(0, (len(words) - 12) // 2)
        out.append(Query('"' + " ".join(words[mid : mid + 12]) + '"', a, z))
    return out


# ---------------------------------------------------------------- Brave + fetching
class BraveClient:
    def __init__(self, client: httpx.Client | None = None):
        s = get_settings()
        self.key = s.BRAVE_API_KEY.get_secret_value()
        self.url = s.BRAVE_API_URL
        self.count = s.WEB_RESULTS_PER_QUERY
        self.limiter = RateLimiter(max(1, int(s.BRAVE_RPS * 60)))
        self.client = client or httpx.Client(timeout=20)

    def search(self, q: str) -> list[dict]:
        self.limiter.wait()
        r = self.client.get(self.url, params={"q": q, "count": self.count, "safesearch": "off"},
                            headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
        if r.status_code == 429:
            raise RuntimeError("brave_rate_limited")
        r.raise_for_status()
        results = (r.json().get("web") or {}).get("results") or []
        return [{"url": x.get("url"), "title": x.get("title") or ""} for x in results if x.get("url")]


def is_public_url(url: str) -> bool:
    try:
        u = urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname or (u.port not in (None, 80, 443)):
            return False
        for info in socket.getaddrinfo(u.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False
        return True
    except (OSError, ValueError):
        return False


@dataclass
class Fetcher:
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=20, follow_redirects=False, headers={"User-Agent": USER_AGENT}))
    url_check: object = None  # defaults to is_public_url (looked up at call time)
    _robots: dict = field(default_factory=dict)

    def allowed(self, url: str) -> bool:
        if not get_settings().WEB_RESPECT_ROBOTS:
            return True
        u = urlparse(url)
        base = f"{u.scheme}://{u.netloc}"
        rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            self._robots[base] = rp
        return rp.can_fetch(USER_AGENT, url)

    def fetch_text(self, url: str) -> tuple[str, str]:
        ctype, data = self.fetch_bytes(url)
        return _to_text(data, ctype)

    def fetch_bytes(self, url: str) -> tuple[str, bytes]:
        """Return (content_type, body). Follows up to 3 redirects, re-checking every hop."""
        limit = get_settings().WEB_MAX_PAGE_MB * 1024 * 1024
        for _ in range(4):
            if not (self.url_check or is_public_url)(url):
                raise ValueError("blocked_url")
            if not self.allowed(url):
                raise ValueError("robots_disallow")
            with self.client.stream("GET", url) as r:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                    url = str(httpx.URL(url).join(r.headers["location"]))
                    continue
                r.raise_for_status()
                ctype = r.headers.get("content-type", "").lower()
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > limit:
                        raise ValueError("too_large")
            return ctype, bytes(buf)
        raise ValueError("too_many_redirects")


def _to_text(data: bytes, ctype: str) -> tuple[str, str]:
    if "pdf" in ctype or data[:5] == b"%PDF-":
        import pymupdf

        pdf = pymupdf.open(stream=data, filetype="pdf")
        return (pdf.metadata or {}).get("title") or "", "\n".join(p.get_text("text") for p in pdf)
    if "html" in ctype or b"<html" in data[:2000].lower():
        from lxml import html as lxml_html

        tree = lxml_html.fromstring(data)
        for bad in tree.xpath("//script|//style|//noscript|//nav|//header|//footer"):
            bad.drop_tree()
        title = (tree.findtext(".//title") or "").strip()
        return title, tree.text_content()
    if ctype.startswith("text/"):
        return "", data.decode("utf-8", errors="replace")
    raise ValueError("unsupported_content")


# ---------------------------------------------------------------- run
def _url_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def page_hashes(db: Session, url: str, title_hint: str, fetcher: Fetcher, stats: dict) -> WebSource | None:
    s = get_settings()
    row = db.scalar(select(WebPageCache).where(WebPageCache.url_hash == _url_key(url)))
    fresh = row is not None and row.fetched_at.replace(tzinfo=row.fetched_at.tzinfo or UTC) > datetime.now(UTC) - timedelta(days=s.WEB_PAGE_CACHE_DAYS)
    if fresh:
        stats["cached_pages"] += 1
        if row.status != "ok":
            return None
        return WebSource(url, row.title or title_hint, set(np.frombuffer(row.hashes, dtype=np.int64).tolist()))
    try:
        title, text = fetcher.fetch_text(url)
        hs = sorted({h for h, _ in shingles(canonical_words(text), canonical_stopwords())})
        status = "ok"
        stats["fetched_pages"] += 1
    except Exception as exc:  # noqa: BLE001 - any fetch/parse problem is recorded, not fatal
        title, hs, status = "", [], str(exc)[:20] or exc.__class__.__name__
        stats["failed_pages"] += 1
    if row is None:
        row = WebPageCache(url_hash=_url_key(url), url=url[:1000])
        db.add(row)
    row.title, row.status, row.word_count = (title or title_hint)[:500], status, len(hs)
    row.hashes = np.array(hs, dtype=np.int64).tobytes()
    row.fetched_at = datetime.now(UTC)
    db.commit()
    return WebSource(url, row.title, set(hs)) if status == "ok" else None


def run(db: Session, stream: TokenStream, covered: np.ndarray, max_queries: int, brave: BraveClient | None = None,
        fetcher: Fetcher | None = None, progress=None, abbreviations: tuple[str, ...] = ()) -> tuple[list[WebSource], dict]:
    s = get_settings()
    stats = {"queries_planned": max_queries, "queries_used": 0, "fetched_pages": 0, "cached_pages": 0, "failed_pages": 0,
             "errors": [], "price_per_1000_usd": s.BRAVE_PRICE_PER_1000_USD}
    if not s.BRAVE_API_KEY.get_secret_value():
        stats["errors"].append("not_configured")
        return [], stats
    brave = brave or BraveClient()
    fetcher = fetcher or Fetcher()
    queries = select_queries(stream, covered, max_queries, abbreviations)
    urls: dict[str, str] = {}
    for i, q in enumerate(queries):
        try:
            for res in brave.search(q.text):
                urls.setdefault(res["url"], res["title"])
            stats["queries_used"] += 1
        except Exception as exc:  # noqa: BLE001
            stats["errors"].append(str(exc)[:80])
            if "rate_limited" in str(exc) or "401" in str(exc) or "403" in str(exc):
                break
        if progress:
            progress(f"web {i + 1}/{len(queries)}")
    sources = []
    for j, (url, title) in enumerate(urls.items()):
        src = page_hashes(db, url, title, fetcher, stats)
        if src:
            sources.append(src)
        if progress:
            progress(f"pages {j + 1}/{len(urls)}")
    stats["cost_usd"] = round(stats["queries_used"] * s.BRAVE_PRICE_PER_1000_USD / 1000.0, 4)
    stats["queries"] = [q.text for q in queries[:100]]
    return sources, stats
