"""Online check modules: scholarly databases, CyberLeninka, patents (Lens.org), legal acts (lex.uz).

Each module searches with the most distinctive sentences of the checked document (the same selection
as the internet check: sentences already found locally are skipped) and compares the returned texts by
shingle fingerprints (and chunk vectors for paraphrase / translation).

Sources and licences
  * OpenAlex (CC0 metadata), Crossref (metadata incl. deposited abstracts), Semantic Scholar (API
    licence: research use), CORE (aggregated open-access full texts, free API key), arXiv (API terms:
    <= 1 request / 3 s): abstracts from the API; full texts only when the record carries an open
    licence (Creative Commons / public domain) or comes from an open-access repository API (CORE).
  * CyberLeninka: open-access articles; its site search is used only if robots.txt allows it.
  * Lens.org patent API (token; free for scholarly use). Google Patents is *not* used: it has no public
    API and its terms do not allow automated querying.
  * lex.uz: official legal acts (not protected by copyright in Uzbekistan); found through Brave
    ("site:lex.uz"), pages fetched honouring robots.txt.
Only fingerprints / vectors are cached, never text.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import numpy as np
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.plagiarism import web
from app.plagiarism.harvest.base import reconstruct_abstract, strip_jats
from app.plagiarism.matcher import TokenStream, WebSource
from app.plagiarism.modules import SCHOLARLY_RPS, scholarly_sources
from app.plagiarism.textnorm import canonical_stopwords
from app.providers.resilience import RateLimiter

log = logging.getLogger(__name__)
API_UA = "AcademicAnalyzer/1.0 (academic plagiarism check; open APIs)"
OPEN_LICENCE = re.compile(r"(^|[^a-z])(cc[-_ ]?(by|0)|creativecommons\.org|public[-_ ]domain|pd$|cc0)", re.I)


def is_open_licence(value: str | None) -> bool:
    return bool(value) and bool(OPEN_LICENCE.search(value))


@dataclass
class SearchQuery:
    text: str  # sentence fragment (relevance search)
    keywords: str  # distinctive words (keyword search APIs)


class Searcher:
    """One API. ``search`` returns candidates; texts are compared, never stored."""

    key = "base"
    rps = 1.0

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=httpx.Timeout(25.0, connect=8.0), headers={"User-Agent": API_UA}, follow_redirects=True)
        self.limiter = RateLimiter(max(1, int(self.rps * 60)))

    def _get(self, url: str, **kw) -> httpx.Response:
        self.limiter.wait()
        r = self.client.get(url, **kw)
        r.raise_for_status()
        return r

    def search(self, q: SearchQuery, limit: int) -> list[web.FetchItem]:  # pragma: no cover - interface
        raise NotImplementedError


def _authors(names) -> str:
    return ", ".join(n for n in names if n)[:300]


class OpenAlexSearch(Searcher):
    key, rps = "openalex", SCHOLARLY_RPS["openalex"]

    def search(self, q, limit):
        s = get_settings()
        params = {"search": q.text, "per-page": limit}
        if s.OPENALEX_EMAIL:
            params["mailto"] = s.OPENALEX_EMAIL
        out = []
        for w in self._get("https://api.openalex.org/works", params=params).json().get("results", []):
            loc = w.get("best_oa_location") or {}
            pdf = loc.get("pdf_url") if is_open_licence(loc.get("license")) else None
            doi = (w.get("doi") or "").replace("https://doi.org/", "")
            out.append(web.FetchItem(
                url=w.get("doi") or w.get("id"), title=w.get("title") or w.get("display_name") or "",
                text=reconstruct_abstract(w.get("abstract_inverted_index")), download=pdf,
                authors=_authors((a.get("author") or {}).get("display_name") for a in w.get("authorships") or []),
                year=w.get("publication_year"),
            ) if (doi or w.get("id")) else None)
        return [x for x in out if x]


class CrossrefSearch(Searcher):
    key, rps = "crossref", SCHOLARLY_RPS["crossref"]

    def search(self, q, limit):
        s = get_settings()
        params = {"query": q.keywords, "rows": limit, "select": "DOI,title,abstract,author,issued,license,link,URL"}
        if s.CROSSREF_MAILTO:
            params["mailto"] = s.CROSSREF_MAILTO
        out = []
        for w in self._get("https://api.crossref.org/works", params=params).json().get("message", {}).get("items", []):
            open_lic = any(is_open_licence(lc.get("URL")) for lc in w.get("license") or [])
            pdf = next((ln.get("URL") for ln in w.get("link") or [] if "pdf" in (ln.get("content-type") or "")), None) if open_lic else None
            year = ((w.get("issued") or {}).get("date-parts") or [[None]])[0][0]
            out.append(web.FetchItem(
                url=f"https://doi.org/{w['DOI']}" if w.get("DOI") else w.get("URL"), title=" ".join(w.get("title") or []),
                text=strip_jats(w.get("abstract")), download=pdf, year=year,
                authors=_authors(" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in w.get("author") or []),
            ))
        return [x for x in out if x.url]


class SemanticScholarSearch(Searcher):
    key, rps = "semanticscholar", SCHOLARLY_RPS["semanticscholar"]

    def search(self, q, limit):
        key = get_settings().SEMANTIC_SCHOLAR_API_KEY.get_secret_value()
        r = self._get("https://api.semanticscholar.org/graph/v1/paper/search",
                      params={"query": q.keywords, "limit": limit, "fields": "title,abstract,year,authors,url,externalIds,openAccessPdf"},
                      headers={"x-api-key": key} if key else {})
        out = []
        for p in r.json().get("data") or []:
            oa = p.get("openAccessPdf") or {}
            pdf = oa.get("url") if is_open_licence(oa.get("license")) else None
            doi = (p.get("externalIds") or {}).get("DOI")
            out.append(web.FetchItem(url=f"https://doi.org/{doi}" if doi else p.get("url"), title=p.get("title") or "",
                                     text=p.get("abstract") or "", download=pdf, year=p.get("year"),
                                     authors=_authors(a.get("name") for a in p.get("authors") or [])))
        return [x for x in out if x.url]


class CoreSearch(Searcher):
    key, rps = "core", SCHOLARLY_RPS["core"]

    def search(self, q, limit):
        token = get_settings().CORE_API_KEY.get_secret_value()
        r = self._get("https://api.core.ac.uk/v3/search/works", params={"q": q.keywords, "limit": limit},
                      headers={"Authorization": f"Bearer {token}"})
        out = []
        for w in r.json().get("results") or []:
            doi = w.get("doi")
            url = f"https://doi.org/{doi}" if doi else (w.get("downloadUrl") or (f"https://core.ac.uk/works/{w['id']}" if w.get("id") else None))
            # CORE serves full texts of open-access repository copies through its API
            out.append(web.FetchItem(url=url, title=w.get("title") or "", text=(w.get("fullText") or w.get("abstract") or "")[:400_000],
                                     year=w.get("yearPublished"), authors=_authors(a.get("name") for a in w.get("authors") or [])))
        return [x for x in out if x.url]


class ArxivSearch(Searcher):
    key, rps = "arxiv", SCHOLARLY_RPS["arxiv"]
    NS = {"a": "http://www.w3.org/2005/Atom"}

    def search(self, q, limit):
        terms = " AND ".join(f"all:{w}" for w in q.keywords.split()[:6])
        r = self._get("https://export.arxiv.org/api/query", params={"search_query": terms, "max_results": limit})
        out = []
        for e in ET.fromstring(r.content).findall("a:entry", self.NS):
            abs_url = (e.findtext("a:id", "", self.NS) or "").strip()
            if not abs_url:
                continue
            pdf = next((ln.get("href") for ln in e.findall("a:link", self.NS) if ln.get("title") == "pdf"), None)
            if pdf:
                pdf = pdf.replace("http://arxiv.org/", "https://export.arxiv.org/").replace("https://arxiv.org/", "https://export.arxiv.org/")
            year = (e.findtext("a:published", "", self.NS) or "")[:4]
            out.append(web.FetchItem(
                url=abs_url, title=" ".join((e.findtext("a:title", "", self.NS) or "").split()),
                text=" ".join((e.findtext("a:summary", "", self.NS) or "").split()),
                # arXiv licences every e-print for distribution; downloads still honour robots.txt
                download=pdf, year=int(year) if year.isdigit() else None,
                authors=_authors(a.findtext("a:name", "", self.NS) for a in e.findall("a:author", self.NS)),
            ))
        return out


class CyberLeninkaSearch(Searcher):
    key, rps = "cyberleninka", 0.5
    API = "https://cyberleninka.ru/api/search"

    def __init__(self, client=None, fetcher: web.Fetcher | None = None):
        super().__init__(client)
        self.fetcher = fetcher

    def search(self, q, limit):
        if self.fetcher is not None and not self.fetcher.allowed(self.API):
            raise RuntimeError("robots_disallow: CyberLeninka robots.txt qidiruvga ruxsat bermaydi")
        self.limiter.wait()
        r = self.client.post(self.API, json={"mode": "articles", "q": q.text, "size": limit, "from": 0})
        r.raise_for_status()
        out = []
        for a in r.json().get("articles") or []:
            link = a.get("link") or ""
            url = "https://cyberleninka.ru" + link if link.startswith("/") else link
            if not url:
                continue
            out.append(web.FetchItem(url=url, title=strip_jats(a.get("name")), text=strip_jats(a.get("annotation")),
                                     download=url + "/pdf", year=a.get("year"), authors=_authors(a.get("authors") or [])))
        return out


class LensPatentSearch(Searcher):
    key, rps = "lens", 0.8
    API = "https://api.lens.org/patent/search"

    def search(self, q, limit):
        token = get_settings().LENS_API_TOKEN.get_secret_value()
        body = {"query": {"query_string": {"query": q.keywords, "fields": ["title", "abstract.text", "claim.text", "description.text"]}},
                "size": limit, "include": ["lens_id", "biblio.invention_title", "abstract", "claims", "description", "date_published"]}
        self.limiter.wait()
        r = self.client.post(self.API, json=body, headers={"Authorization": f"Bearer {token}"})
        if r.status_code in (401, 403):
            raise RuntimeError(f"lens_auth_{r.status_code}: Lens.org tokeni noto'g'ri yoki muddati o'tgan")
        r.raise_for_status()
        out = []
        for p in r.json().get("data") or []:
            titles = (p.get("biblio") or {}).get("invention_title") or []
            parts = [a.get("text", "") for a in p.get("abstract") or []]
            for c in p.get("claims") or []:
                for cl in c.get("claims") or []:
                    parts.extend(cl.get("claim_text") or [])
            desc = p.get("description")
            if isinstance(desc, dict):
                parts.append(desc.get("text") or "")
            year = (p.get("date_published") or "")[:4]
            out.append(web.FetchItem(url=f"https://www.lens.org/lens/patent/{p.get('lens_id')}",
                                     title=(titles[0].get("text") if titles else "") or p.get("lens_id", ""),
                                     text="\n".join(x for x in parts if x)[:400_000], year=int(year) if year.isdigit() else None))
        return out


SCHOLARLY = {"openalex": OpenAlexSearch, "crossref": CrossrefSearch, "semanticscholar": SemanticScholarSearch,
             "core": CoreSearch, "arxiv": ArxivSearch}


def make_queries(stream: TokenStream, covered: np.ndarray, n: int, abbreviations=()) -> list[SearchQuery]:
    stop = canonical_stopwords()
    out = []
    for q in web.select_queries(stream, covered, n, abbreviations):
        kws = [stream.words[i] for i in range(q.token_start, q.token_end)
               if stream.canon[i] not in stop and len(stream.canon[i]) > 3 and stream.words[i].isalpha()]
        out.append(SearchQuery(q.text, " ".join(dict.fromkeys(kws))[:200] or q.text))
    return out


def _error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http_{exc.response.status_code}"
    if isinstance(exc, httpx.HTTPError):
        return f"connection_error: {exc}"[:120]
    return str(exc)[:160]


def run_module(db: Session, key: str, stream: TokenStream, covered: np.ndarray, n_queries: int, *,
               searchers: dict[str, Searcher] | None = None, fetcher: web.Fetcher | None = None, progress: Callable | None = None,
               with_vectors: bool = False, abbreviations=()) -> tuple[list[WebSource], dict]:
    """Run one online module (scholarly | cyberleninka | patents). Returns (sources, stats)."""
    s = get_settings()
    fetcher = fetcher or web.Fetcher()
    if searchers is None:
        if key == "scholarly":
            searchers = {name: SCHOLARLY[name]() for name in scholarly_sources()}
        elif key == "cyberleninka":
            searchers = {"cyberleninka": CyberLeninkaSearch(fetcher=fetcher)}
        elif key == "patents":
            searchers = {"lens": LensPatentSearch()}
        else:
            raise ValueError(key)
    stats = {"module": key, "queries_planned": n_queries, "requests": 0, "results_total": 0, "errors": [], "query_log": [],
             "per_source": {name: {"requests": 0, "results": 0, "errors": 0} for name in searchers}, "pages": [],
             "fetched_pages": 0, "cached_pages": 0, "failed_pages": 0, "cost_usd": 0.0}
    queries = make_queries(stream, covered, n_queries, abbreviations)
    if not queries:
        stats["errors"].append("no_query_sentences: onlayn qidirish uchun mos jumla qolmadi")
        return [], stats
    items: dict[str, web.FetchItem] = {}
    downloads_per_query = s.MODULE_FULLTEXT_PER_QUERY
    dead: set[str] = set()
    for i, q in enumerate(queries):
        for name, searcher in searchers.items():
            if name in dead:
                continue
            ps = stats["per_source"][name]
            try:
                found = searcher.search(q, s.MODULE_RESULTS_PER_QUERY)
                ps["requests"] += 1
                stats["requests"] += 1
                ps["results"] += len(found)
                stats["results_total"] += len(found)
                stats["query_log"].append({"q": q.text, "source": name, "results": len(found)})
                taken = 0
                for it in found:
                    if it.url in items:
                        continue
                    if it.download and taken >= downloads_per_query:
                        it.download = None  # keep the abstract, skip the extra download
                    taken += bool(it.download)
                    items[it.url] = it
            except Exception as exc:  # noqa: BLE001 - one failing API never stops the others
                ps["errors"] += 1
                msg = f"{name}: {_error(exc)}"
                stats["errors"].append(msg)
                stats["query_log"].append({"q": q.text, "source": name, "results": None, "error": msg[:80]})
                if ps["errors"] >= 3 or "auth" in msg or "robots_disallow" in msg or "connection_error" in msg:
                    dead.add(name)  # stop calling an API that keeps failing
        if progress:
            progress(f"{key} {i + 1}/{len(queries)}")
    cands = list(items.values())[: s.WEB_MAX_PAGES]
    sources = [src for src in web.build_sources(db, cands, fetcher, stats, key, progress, with_vectors) if src]
    if stats["requests"] and not stats["results_total"]:
        stats["errors"].append("no_results: hech bir so'rovga natija qaytmadi")
    stats["queries"] = [q.text for q in queries]
    return sources, stats
