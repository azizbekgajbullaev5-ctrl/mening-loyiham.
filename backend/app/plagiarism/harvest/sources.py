"""Harvesters for open scholarly sources.

* OJS journals (OAI-PMH ``oai_dc``) — many Uzbek journals run Open Journal Systems.
* OpenAlex      — https://api.openalex.org (open access works; abstract + OA PDF).
* CORE          — https://api.core.ac.uk/v3 (needs CORE_API_KEY; returns full text).
* Crossref      — https://api.crossref.org (metadata/abstracts; open PDF links when present).
* CyberLeninka  — public search endpoint used by its website (unofficial, may change).

Each harvester yields HarvestItem; full text is fetched only when
HARVEST_FETCH_FULLTEXT is on and the link is a public http(s) URL.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from urllib.parse import urljoin

from lxml import etree

from app.core.config import get_settings
from app.plagiarism.harvest.base import Harvester, HarvestItem, reconstruct_abstract, strip_jats

OAI_NS = {"oai": "http://www.openarchives.org/OAI/2.0/", "dc": "http://purl.org/dc/elements/1.1/",
          "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/"}


def _year(value: str | None) -> int | None:
    m = re.search(r"(19|20)\d{2}", value or "")
    return int(m.group(0)) if m else None


class OJSHarvester(Harvester):
    """``target`` = journal base URL, e.g. https://journal.example.uz/index.php/jname"""

    source_type = "ojs"

    def harvest(self, target: str, limit: int) -> Iterator[HarvestItem]:
        base = target.rstrip("/")
        endpoint = base if base.endswith("/oai") else base + "/oai"
        if not self._robots_ok(endpoint):
            raise RuntimeError("robots_disallow: jurnal robots.txt OAI-PMH ga ruxsat bermaydi")
        params: dict = {"verb": "ListRecords", "metadataPrefix": "oai_dc"}
        n = 0
        while n < limit:
            root = etree.fromstring(self.get(endpoint, params=params).content)
            for rec in root.iterfind(".//oai:record", OAI_NS):
                if rec.find("oai:header", OAI_NS) is not None and rec.find("oai:header", OAI_NS).get("status") == "deleted":
                    continue
                md = rec.find(".//oai_dc:dc", OAI_NS)
                if md is None:
                    continue
                vals = lambda tag: [e.text.strip() for e in md.iterfind(f"dc:{tag}", OAI_NS) if e.text and e.text.strip()]  # noqa: E731
                titles, desc, ids = vals("title"), vals("description"), vals("identifier")
                url = next((i for i in ids if i.startswith("http") and "/article/view/" in i), next((i for i in ids if i.startswith("http")), None))
                doi = next((i.split("doi.org/")[-1] for i in ids if "doi" in i.lower() and "10." in i), None)
                item = HarvestItem(
                    "ojs", titles[0] if titles else "(untitled)", "\n".join(titles[:1] + desc), "; ".join(vals("creator"))[:500],
                    _year(" ".join(vals("date"))), doi, url, extra={"language": (vals("language") or [""])[0]},
                )
                if url and get_settings().HARVEST_FETCH_FULLTEXT:
                    # resolved only for new articles (after the duplicate check), so re-harvesting a journal is cheap
                    item.extra["resolve_pdf"] = lambda url=url: self._galley_pdf(url)
                yield item
                n += 1
                if n >= limit:
                    return
            token = root.find(".//oai:resumptionToken", OAI_NS)
            if token is None or not (token.text or "").strip():
                return
            params = {"verb": "ListRecords", "resumptionToken": token.text.strip()}

    def _robots_ok(self, url: str) -> bool:
        from app.plagiarism.web import Fetcher

        if not hasattr(self, "_fetcher"):
            self._fetcher = Fetcher()
        return self._fetcher.allowed(url)

    def _galley_pdf(self, article_url: str) -> str | None:
        """OJS article page -> first PDF galley download link (only if robots.txt allows the page)."""
        try:
            if not self._robots_ok(article_url):
                return None
            html = self.get(article_url).text
        except Exception:  # noqa: BLE001
            return None
        for href in re.findall(r'href="([^"]+/article/(?:view|download)/\d+/\d+[^"]*)"', html):
            return urljoin(article_url, href.replace("/article/view/", "/article/download/"))
        return None


class OpenAlexHarvester(Harvester):
    source_type = "openalex"

    def harvest(self, target: str, limit: int) -> Iterator[HarvestItem]:
        s = get_settings()
        cursor, n = "*", 0
        while n < limit and cursor:
            params = {"search": target, "per-page": min(50, limit - n), "cursor": cursor}
            if s.OPENALEX_FILTER:
                params["filter"] = s.OPENALEX_FILTER
            if s.OPENALEX_EMAIL:
                params["mailto"] = s.OPENALEX_EMAIL
            data = self.get("https://api.openalex.org/works", params=params).json()
            for w in data.get("results", []):
                title = w.get("title") or w.get("display_name") or "(untitled)"
                abstract = reconstruct_abstract(w.get("abstract_inverted_index"))
                loc = w.get("best_oa_location") or {}
                yield HarvestItem(
                    "openalex", title, f"{title}\n{abstract}",
                    "; ".join(a.get("author", {}).get("display_name", "") for a in w.get("authorships", [])[:10]),
                    w.get("publication_year"), (w.get("doi") or "").split("doi.org/")[-1] or None,
                    loc.get("landing_page_url") or w.get("id"), pdf_url=loc.get("pdf_url"), extra={"language": w.get("language")},
                )
                n += 1
                if n >= limit:
                    return
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not data.get("results"):
                return


class CoreHarvester(Harvester):
    source_type = "core"

    def harvest(self, target: str, limit: int) -> Iterator[HarvestItem]:
        key = get_settings().CORE_API_KEY.get_secret_value()
        if not key:
            raise RuntimeError("CORE_API_KEY not configured")
        offset = 0
        while offset < limit:
            data = self.get("https://api.core.ac.uk/v3/search/works", params={"q": target, "limit": min(50, limit - offset), "offset": offset},
                            headers={"Authorization": f"Bearer {key}"}).json()
            results = data.get("results", [])
            for w in results:
                full = w.get("fullText") or ""
                title = w.get("title") or "(untitled)"
                yield HarvestItem(
                    "core", title, full or f"{title}\n{w.get('abstract') or ''}", "; ".join(a.get("name", "") for a in (w.get("authors") or [])[:10]),
                    w.get("yearPublished"), w.get("doi"), w.get("downloadUrl") or (w.get("links") or [{}])[0].get("url"),
                    fulltext=bool(full), extra={"language": (w.get("language") or {}).get("code")},
                )
            if not results:
                return
            offset += len(results)


class CrossrefHarvester(Harvester):
    source_type = "crossref"

    def harvest(self, target: str, limit: int) -> Iterator[HarvestItem]:
        s = get_settings()
        offset = 0
        while offset < limit:
            params = {"query": target, "rows": min(50, limit - offset), "offset": offset, "filter": "has-abstract:true"}
            if s.CROSSREF_MAILTO:
                params["mailto"] = s.CROSSREF_MAILTO
            items = self.get("https://api.crossref.org/works", params=params).json().get("message", {}).get("items", [])
            for w in items:
                title = (w.get("title") or ["(untitled)"])[0]
                authors = "; ".join(f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (w.get("author") or [])[:10])
                year = ((w.get("issued") or {}).get("date-parts") or [[None]])[0][0]
                pdf = next((ln.get("URL") for ln in w.get("link") or [] if "pdf" in (ln.get("content-type") or "")), None)
                yield HarvestItem("crossref", title, f"{title}\n{strip_jats(w.get('abstract'))}", authors, year, w.get("DOI"),
                                  w.get("URL"), pdf_url=pdf, extra={"language": w.get("language")})
            if not items:
                return
            offset += len(items)


class CyberLeninkaHarvester(Harvester):
    """Uses the JSON search endpoint of cyberleninka.ru (not an official API)."""

    source_type = "cyberleninka"

    def harvest(self, target: str, limit: int) -> Iterator[HarvestItem]:
        offset = 0
        while offset < limit:
            self.limiter.wait()
            r = self.client.post("https://cyberleninka.ru/api/search", json={"mode": "articles", "q": target, "size": min(20, limit - offset), "from": offset})
            r.raise_for_status()
            arts = r.json().get("articles", [])
            for a in arts:
                link = a.get("link") or ""
                url = "https://cyberleninka.ru" + link if link.startswith("/") else link
                title = re.sub(r"<[^>]+>", "", a.get("name") or "(untitled)")
                abstract = re.sub(r"<[^>]+>", "", a.get("annotation") or "")
                yield HarvestItem("cyberleninka", title, f"{title}\n{abstract}", "; ".join(a.get("authors") or [])[:500],
                                  _year(str(a.get("year") or "")), None, url, pdf_url=(url + "/pdf") if url else None)
            if not arts:
                return
            offset += len(arts)


HARVESTERS = {
    "ojs": OJSHarvester,
    "openalex": OpenAlexHarvester,
    "core": CoreHarvester,
    "crossref": CrossrefHarvester,
    "cyberleninka": CyberLeninkaHarvester,
}
