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
import threading
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor, as_completed
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
# Many sites answer 403 to an unknown bot UA; this one is browser-compatible but still names the tool.
USER_AGENT = "Mozilla/5.0 (compatible; AcademicAnalyzer/1.0; academic plagiarism check; respects robots.txt)"
ROBOTS_AGENT = "AcademicAnalyzer"
_HEADERS = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5",
            "Accept-Language": "uz,ru;q=0.9,en;q=0.8"}
_TIMEOUT = httpx.Timeout(20.0, connect=8.0)
QUERY_WORDS = 18
QUERY_MAX_CHARS = 350  # Brave accepts up to 400 characters / 50 words
FAILED_PAGE_CACHE_HOURS = 24  # retry pages that failed (timeouts, 5xx) after a day, not after WEB_PAGE_CACHE_DAYS
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
        out.append(Query(_query_text(stream.words[a:z]), a, z))
    return out


def _query_text(words: list[str]) -> str:
    """A plain (unquoted) query of up to QUERY_WORDS words from the middle of the sentence.

    A quoted 12-word exact phrase almost never matches for Uzbek text (apostrophe variants o'/oʻ/o‘, word
    forms, hyphenation on the source page), so Brave returned no results at all. A plain query still ranks
    pages containing the sentence first; whether a page really matches is decided by shingle comparison.
    """
    words = [w for w in words if any(ch.isalnum() for ch in w)]
    mid = max(0, (len(words) - QUERY_WORDS) // 2)
    text = " ".join(words[mid : mid + QUERY_WORDS])
    return text[:QUERY_MAX_CHARS].rsplit(" ", 1)[0] if len(text) > QUERY_MAX_CHARS else text


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
        if r.status_code in (401, 403):
            raise RuntimeError(f"brave_auth_{r.status_code}: API kaliti noto'g'ri yoki tarif ruxsat bermaydi")
        if r.status_code == 422:
            raise RuntimeError(f"brave_bad_request_422: {r.text[:120]}")
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
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=_TIMEOUT, follow_redirects=False, headers=_HEADERS))
    url_check: object = None  # defaults to is_public_url (looked up at call time)
    _robots: dict = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def allowed(self, url: str) -> bool:
        if not get_settings().WEB_RESPECT_ROBOTS:
            return True
        u = urlparse(url)
        base = f"{u.scheme}://{u.netloc}"
        with self._lock:
            rp = self._robots.get(base)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt")
                if r.status_code in (301, 302, 307, 308) and r.headers.get("location"):
                    nxt = str(httpx.URL(base + "/robots.txt").join(r.headers["location"]))
                    r = self.client.get(nxt) if (self.url_check or is_public_url)(nxt) else r
                # RFC 9309: unreachable (4xx) robots.txt means "allowed"; server errors mean "disallowed"
                if r.status_code >= 500:
                    rp.parse(["User-agent: *", "Disallow: /"])
                else:
                    rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            with self._lock:
                self._robots[base] = rp
        return rp.can_fetch(ROBOTS_AGENT, url)

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


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http_{exc.response.status_code}"
    if isinstance(exc, httpx.HTTPError):
        return "connection_error"
    msg = str(exc)
    if msg in ("blocked_url", "robots_disallow", "too_large", "too_many_redirects", "unsupported_content"):
        return msg
    return "parse_error"


def _cached(db: Session, url: str) -> WebPageCache | None:
    s = get_settings()
    row = db.scalar(select(WebPageCache).where(WebPageCache.url_hash == _url_key(url)))
    if row is None:
        return None
    age = datetime.now(UTC) - row.fetched_at.replace(tzinfo=row.fetched_at.tzinfo or UTC)
    limit = timedelta(days=s.WEB_PAGE_CACHE_DAYS) if row.status == "ok" else timedelta(hours=FAILED_PAGE_CACHE_HOURS)
    return row if age < limit else None


def _download(fetcher: Fetcher, url: str) -> tuple[str, str, str]:
    """(title, text, status) — runs in a worker thread, no DB access. The text is used in memory only."""
    try:
        title, text = fetcher.fetch_text(url)
        return title, text, "ok"
    except Exception as exc:  # noqa: BLE001 - any fetch/parse problem is recorded, not fatal
        return "", "", _failure_code(exc)


def text_hashes(text: str) -> tuple[list[int], int]:
    words = canonical_words(text)
    return sorted({h for h, _ in shingles(words, canonical_stopwords())}), len(words)


MAX_VECTOR_CHUNKS = 400


def text_vectors(text: str) -> tuple[np.ndarray | None, str]:
    """Chunk embeddings of a source text (for paraphrase / translation matching) and the backend key."""
    from app.plagiarism import embeddings
    from app.plagiarism.textnorm import display_text, tokenize

    be = embeddings.get_backend()
    disp = display_text(text)
    toks = tokenize(disp)
    if len(toks) < 30:
        return None, f"{be.id}|{be.dims}"
    canon = [t.text for t in toks]
    words = canon if isinstance(be, embeddings.HashBackend) else [disp[t.start : t.end] for t in toks]
    spans = embeddings.chunk_windows(canon)[:MAX_VECTOR_CHUNKS]
    return be.encode([" ".join(words[a:b]) for a, b in spans]), f"{be.id}|{be.dims}"


def text_language(text: str) -> str | None:
    from app.analyzers.languages.registry import detect_distribution

    paras = [p for p in text.split("\n") if len(p) > 40][:60] or [text[:3000]]
    lang, _, _ = detect_distribution(paras)
    return lang if lang and lang != "unknown" else None


def _store(db: Session, url: str, title: str, hs: list[int], status: str, words: int, module: str = "web",
           language: str | None = None, vectors: np.ndarray | None = None, backend: str | None = None) -> None:
    row = db.scalar(select(WebPageCache).where(WebPageCache.url_hash == _url_key(url)))
    if row is None:
        row = WebPageCache(url_hash=_url_key(url), url=url[:1000])
        db.add(row)
    row.title, row.status, row.word_count, row.module, row.language = title[:500], status, words, module, language
    row.hashes = np.array(hs, dtype=np.int64).tobytes()
    row.vectors = vectors.astype(np.float16).tobytes() if vectors is not None and len(vectors) else None
    row.vector_backend = backend if row.vectors else None
    row.fetched_at = datetime.now(UTC)
    db.commit()


def _row_vectors(row: WebPageCache) -> np.ndarray | None:
    if not row.vectors or not row.vector_backend:
        return None
    from app.plagiarism import embeddings

    be = embeddings.get_backend()
    if row.vector_backend != f"{be.id}|{be.dims}":
        return None  # another embedding backend: not comparable
    return np.frombuffer(row.vectors, dtype=np.float16).astype(np.float32).reshape(-1, be.dims)


@dataclass
class FetchItem:
    """One candidate source. ``text`` comes from an API (abstract, claims, CORE full text); ``download`` is
    a page or open-licence PDF fetched honouring robots.txt. ``url`` is what the report links to."""

    url: str
    title: str = ""
    text: str = ""
    download: str | None = None
    authors: str = ""
    year: int | None = None


def page_hashes(db: Session, url: str, title_hint: str, fetcher: Fetcher, stats: dict) -> WebSource | None:
    """Fingerprints of one page (cache first). Also appends a record to stats["pages"]."""
    return fetch_pages(db, [(url, title_hint)], fetcher, stats)[0]


def fetch_pages(db: Session, items: list[tuple[str, str]], fetcher: Fetcher, stats: dict, progress=None,
                module: str = "web", with_vectors: bool = False) -> list[WebSource | None]:
    return build_sources(db, [FetchItem(url, hint, download=url) for url, hint in items], fetcher, stats, module, progress, with_vectors)


def build_sources(db: Session, items: list[FetchItem], fetcher: Fetcher, stats: dict, module: str = "web", progress=None,
                  with_vectors: bool = False) -> list[WebSource | None]:
    """Turn candidates into comparable sources (shingle hashes, optionally chunk vectors). Downloads are cached
    by URL (fingerprints / vectors only). Every candidate gets a record in stats["pages"]."""
    for key in ("pages",):
        stats.setdefault(key, [])
    for key in ("cached_pages", "fetched_pages", "failed_pages"):
        stats.setdefault(key, 0)
    downloaded: dict[str, tuple[str, list[int], str, int, np.ndarray | None, str | None]] = {}
    todo = []
    for it in items:
        if not it.download or it.download in downloaded:
            continue
        row = _cached(db, it.download)
        if row is None:
            todo.append(it.download)
            continue
        stats["cached_pages"] += 1
        hs = np.frombuffer(row.hashes, dtype=np.int64).tolist() if row.status == "ok" else []
        downloaded[it.download] = (row.title, hs, row.status, row.word_count, _row_vectors(row) if with_vectors else None, row.language)
        stats["pages"].append({"url": it.download, "source_url": it.url, "title": row.title or it.title, "status": row.status,
                               "cached": True, "words": row.word_count, "module": module})
    workers = max(1, get_settings().WEB_FETCH_WORKERS)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download, fetcher, url): url for url in dict.fromkeys(todo)}
        for k, fut in enumerate(as_completed(futures), 1):
            url = futures[fut]
            title, text, status = fut.result()
            hs, words = text_hashes(text) if status == "ok" else ([], 0)
            if status == "ok" and not hs:
                status = "no_text"
            vecs, backend = text_vectors(text) if (with_vectors and status == "ok") else (None, None)
            lang = text_language(text) if status == "ok" else None
            _store(db, url, title, hs, status, words, module, lang, vecs, backend)
            stats["fetched_pages" if status == "ok" else "failed_pages"] += 1
            hint = next((it for it in items if it.download == url), None)
            stats["pages"].append({"url": url, "source_url": hint.url if hint else url, "title": title or (hint.title if hint else ""),
                                   "status": status, "cached": False, "words": words, "module": module})
            downloaded[url] = (title, hs, status, words, vecs, lang)
            if progress:
                progress(f"{module} {k}/{len(futures)}")
    out: list[WebSource | None] = []
    for it in items:
        hashes: set[int] = set()
        vec_parts, lang, title = [], None, it.title
        if it.text:
            hs, words = text_hashes(it.text)
            hashes.update(hs)
            if with_vectors:
                v, _ = text_vectors(it.text)
                if v is not None:
                    vec_parts.append(v)
            lang = text_language(it.text)
            if not it.download:
                stats["pages"].append({"url": it.url, "source_url": it.url, "title": it.title, "status": "api_text" if hs else "no_text",
                                       "cached": False, "words": words, "module": module})
        if it.download and it.download in downloaded:
            d_title, d_hs, d_status, _w, d_vec, d_lang = downloaded[it.download]
            if d_status == "ok":
                hashes.update(d_hs)
                title = title or d_title
                lang = lang or d_lang
                if d_vec is not None:
                    vec_parts.append(d_vec)
        if not hashes:
            out.append(None)
            continue
        vectors = np.vstack(vec_parts) if vec_parts else None
        out.append(WebSource(it.url, title or it.url, hashes, module=module, authors=it.authors, year=it.year, vectors=vectors, language=lang))
    return out


def run(db: Session, stream: TokenStream, covered: np.ndarray, max_queries: int, brave: BraveClient | None = None,
        fetcher: Fetcher | None = None, progress=None, abbreviations: tuple[str, ...] = (), module: str = "web",
        site: str | None = None, with_vectors: bool = False) -> tuple[list[WebSource], dict]:
    """Search Brave for distinctive sentences and compare the found pages. ``site`` restricts the search
    (the lex.uz module uses ``site:lex.uz``)."""
    s = get_settings()
    stats = {"queries_planned": max_queries, "queries_used": 0, "fetched_pages": 0, "cached_pages": 0, "failed_pages": 0,
             "results_total": 0, "queries_without_results": 0, "errors": [], "pages": [], "query_log": [],
             "price_per_1000_usd": s.BRAVE_PRICE_PER_1000_USD}
    if not s.BRAVE_API_KEY.get_secret_value():
        stats["errors"].append("not_configured")
        return [], stats
    brave = brave or BraveClient()
    fetcher = fetcher or Fetcher()
    queries = select_queries(stream, covered, max_queries, abbreviations)
    if not queries:
        stats["errors"].append("no_query_sentences: tekshirilmagan (bazada topilmagan) mos jumla qolmadi")
    urls: dict[str, str] = {}
    for i, q in enumerate(queries):
        try:
            found = brave.search(f"site:{site} {q.text}" if site else q.text)
            if site:
                found = [r for r in found if _on_site(r["url"], site)]
            stats["queries_used"] += 1
            stats["results_total"] += len(found)
            if not found:
                stats["queries_without_results"] += 1
            stats["query_log"].append({"q": q.text, "results": len(found)})
            for res in found:
                urls.setdefault(res["url"], res["title"])
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, httpx.TimeoutException):
                msg = "brave_timeout: Brave javob bermadi (timeout)"
            elif isinstance(exc, httpx.HTTPError) and not isinstance(exc, httpx.HTTPStatusError):
                msg = f"brave_connection: Brave'ga ulanib bo'lmadi ({exc})"  # no internet, proxy or firewall
            else:
                msg = str(exc)
            stats["errors"].append(msg[:160])
            stats["query_log"].append({"q": q.text, "results": None, "error": msg[:80]})
            if "rate_limited" in msg or "brave_auth" in msg or "brave_connection" in msg:
                break
        if progress:
            progress(f"{module} {i + 1}/{len(queries)}")
    if stats["queries_used"] and not stats["results_total"]:
        stats["errors"].append("brave_no_results: Brave hech bir so'rovga natija qaytarmadi")
    items = list(urls.items())[: s.WEB_MAX_PAGES]
    sources = [src for src in fetch_pages(db, items, fetcher, stats, progress, module, with_vectors) if src]
    if items and not sources:
        codes = sorted({p["status"] for p in stats["pages"]})
        stats["errors"].append(f"pages_failed: hech bir sahifa yuklanmadi ({', '.join(codes)})")
    stats["cost_usd"] = round(stats["queries_used"] * s.BRAVE_PRICE_PER_1000_USD / 1000.0, 4)
    stats["queries"] = [q.text for q in queries[:200]]
    return sources, stats


def _on_site(url: str, site: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == site or host.endswith("." + site)
