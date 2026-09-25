"""Plagiarism check modules (Antiplag-style): each one is a separately switchable source or filter.

Every analysis stores the list of enabled modules (``Analysis.check_modules``). Before an analysis
with online modules starts, the user sees the number of requests and the approximate price per
module and confirms. The report states "checked in N of M modules".

Only open sources and APIs whose terms allow this use are queried; pages and PDFs are downloaded
honouring robots.txt (see web.Fetcher), full texts only under open licences, and only fingerprints /
vectors are cached — never the text.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import csv_list, get_settings


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    kind: str  # "local" | "online"
    description: str
    paid: bool = False


MODULES: list[Module] = [
    Module("corpus", "Ma'lumotnoma bazasi", "local", "Siz yuklagan darslik, maqola, dissertatsiya va avtoreferatlar (so'zma-so'z va parafraz)."),
    Module("own", "Sizning hujjatlaringiz", "local", "Oldin yuklagan boshqa hujjatlaringiz (shu hujjatning nusxalari hisobga olinmaydi)."),
    Module("ojs", "O'zbek OJS jurnallari", "local", "Sozlamalardagi OJS jurnallaridan OAI-PMH orqali yig'ilgan maqolalar."),
    Module("scholarly", "Ilmiy bazalar", "online", "OpenAlex, Crossref, Semantic Scholar, CORE, arXiv: annotatsiyalar va ochiq litsenziyali to'liq matnlar."),
    Module("cyberleninka", "CyberLeninka", "online", "Ochiq rus tilidagi ilmiy maqolalar."),
    Module("patents", "Patentlar (Lens.org)", "online", "Lens.org patent API: annotatsiya, formula va tavsif matnlari."),
    Module("legal", "Me'yoriy hujjatlar (lex.uz)", "online", "lex.uz ochiq sahifalari (Brave orqali qidiriladi).", paid=True),
    Module("web", "Internet (Brave)", "online", "Butun internet: eng o'ziga xos jumlalar Brave Search orqali qidiriladi.", paid=True),
    Module("translation", "Tarjima qilingan o'zlashtirish", "local", "Boshqa tildagi (o'zbek ↔ rus ↔ ingliz) manbadan tarjima: ko'p tilli embedding."),
    Module("templates", "Shablon iboralar", "local", "\"Dolzarbligi shundaki\", \"ushbu ishda\" kabi standart iboralar o'zlashtirishga qo'shilmaydi."),
]
BY_KEY = {m.key: m for m in MODULES}
ONLINE = {m.key for m in MODULES if m.kind == "online"}
SCHOLARLY_RPS = {"openalex": 5.0, "crossref": 5.0, "semanticscholar": 1.0, "core": 1.0, "arxiv": 1 / 3}  # polite limits


def normalize(keys) -> list[str]:
    seen = []
    for k in keys or []:
        k = str(k).strip()
        if k in BY_KEY and k not in seen:
            seen.append(k)
    return seen


def default_modules() -> list[str]:
    return normalize(csv_list(get_settings().DEFAULT_CHECK_MODULES))


def from_legacy(corpus_check: bool, web_check: bool) -> list[str]:
    keys = [k for k in default_modules() if k not in ("corpus", "web") and BY_KEY[k].kind == "local"]
    if corpus_check:
        keys = ["corpus", *keys]
    if web_check:
        keys.append("web")
    return normalize(keys)


def enabled_for(analysis) -> list[str]:
    return normalize(analysis.check_modules) or from_legacy(analysis.corpus_check, analysis.web_check)


def scholarly_sources() -> list[str]:
    s = get_settings()
    out = []
    for src in csv_list(s.SCHOLARLY_SOURCES):
        if src == "core" and not s.CORE_API_KEY.get_secret_value():
            continue
        if src in SCHOLARLY_RPS:
            out.append(src)
    return out


def availability(key: str, db: Session | None = None) -> tuple[bool, str]:
    """(usable now, reason shown to the user when not)."""
    from app.plagiarism import embeddings

    s = get_settings()
    brave = bool(s.BRAVE_API_KEY.get_secret_value())
    if key in ("web", "legal") and not brave:
        return False, "Brave API kaliti sozlanmagan (BRAVE_API_KEY)"
    if key == "patents" and not s.LENS_API_TOKEN.get_secret_value():
        return False, "Lens.org tokeni sozlanmagan (LENS_API_TOKEN)"
    if key == "scholarly" and not scholarly_sources():
        return False, "SCHOLARLY_SOURCES bo'sh"
    if key == "translation" and embeddings.expected_kind() == "hash":
        return False, ("ko'p tilli model yo'q: hozir oddiy (hash) vektorlar ishlatilmoqda. Model bir marta internet orqali "
                       "yuklanadi (~0,5 GB); qanday yoqish — yo'riqnomada")
    if key == "ojs" and db is not None:
        from app.models import RefDocument

        n = db.scalar(select(func.count()).select_from(RefDocument).where(RefDocument.source_type == "ojs")) or 0
        if not n and not csv_list(s.HARVEST_OJS_URLS):
            return False, "OJS jurnallari sozlanmagan va bazada OJS maqolalari yo'q (HARVEST_OJS_URLS)"
    return True, ""


def module_queries(key: str, words: int) -> int:
    s = get_settings()
    if words <= 0 or key not in ONLINE:
        return 0
    if key == "web":
        from app.plagiarism import web

        return web.planned_queries(words)
    return int(min(s.MODULE_MAX_QUERIES, max(2, math.ceil(words / s.MODULE_WORDS_PER_QUERY))))


def estimate(words: int, keys: list[str] | None = None, db: Session | None = None) -> dict:
    """Per-module requests / price / time, shown before the check. Free APIs cost $0 but are rate-limited."""
    s = get_settings()
    price = s.BRAVE_PRICE_PER_1000_USD
    rows = {}
    for m in MODULES:
        ok, reason = availability(m.key, db)
        q = module_queries(m.key, words)
        row = {"key": m.key, "label": m.label, "kind": m.kind, "available": ok, "reason": reason, "queries": q,
               "requests": 0, "downloads": 0, "cost_usd": 0.0, "seconds": 0, "paid": m.paid, "description": m.description}
        if m.key == "web":
            row.update(requests=q, downloads=q * s.WEB_RESULTS_PER_QUERY, cost_usd=round(q * price / 1000, 4),
                       seconds=int(q / max(s.BRAVE_RPS, 0.1) + q * s.WEB_RESULTS_PER_QUERY * 2 / max(1, s.WEB_FETCH_WORKERS)))
        elif m.key == "legal":
            row.update(requests=q, downloads=q * 3, cost_usd=round(q * price / 1000, 4), seconds=int(q / max(s.BRAVE_RPS, 0.1) + q * 3))
        elif m.key == "scholarly":
            srcs = scholarly_sources()
            row["sources"] = srcs
            row.update(requests=q * len(srcs), downloads=q * s.MODULE_FULLTEXT_PER_QUERY,
                       seconds=int(sum(q / SCHOLARLY_RPS[x] for x in srcs) + q * s.MODULE_FULLTEXT_PER_QUERY * 2))
        elif m.key == "cyberleninka":
            row.update(requests=q, downloads=q * s.MODULE_FULLTEXT_PER_QUERY, seconds=int(q * (1 + 2 * s.MODULE_FULLTEXT_PER_QUERY)))
        elif m.key == "patents":
            row.update(requests=q, seconds=int(q * 1.5))
        rows[m.key] = row
    selected = normalize(keys) if keys is not None else default_modules()
    active = [k for k in selected if rows[k]["available"]]
    web_row = rows["web"]
    return {
        "words": words,
        "modules": rows,
        "selected": selected,
        "total_cost_usd": round(sum(rows[k]["cost_usd"] for k in active), 4),
        "total_requests": sum(rows[k]["requests"] for k in active),
        "total_seconds": sum(rows[k]["seconds"] for k in active),
        "price_per_1000_usd": price,
        # legacy fields (internet check only), kept for older clients
        "queries": web_row["queries"], "max_pages": web_row["downloads"], "cost_usd": web_row["cost_usd"],
        "configured": web_row["available"],
        "note": "Yuqori chegara: bazada allaqachon topilgan jumlalar onlayn qidirilmaydi, shuning uchun haqiqiy so'rovlar odatda kamroq.",
    }


def needs_confirmation(keys: list[str]) -> bool:
    return any(k in ONLINE for k in keys)
