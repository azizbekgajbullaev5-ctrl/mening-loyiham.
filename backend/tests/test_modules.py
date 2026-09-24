"""Antiplag-style check modules: registry/estimates, online sources (mocked APIs), OJS, translation,
template phrases, bulk corpus import."""
import io
import zipfile

import httpx
import numpy as np
import pytest
from pydantic import SecretStr

from app.core import config
from app.core.database import SessionLocal
from app.models import CorpusJob, RefDocument
from app.plagiarism import corpus, embeddings, web
from tests.conftest import upload
from tests.fixtures.sample_texts import SAMPLES
from tests.test_plagiarism import _clean_corpus, _pdf_bytes, admin, corpus_upload, make_docx  # noqa: F401 - fixtures

UZ, RU = SAMPLES["uz"], SAMPLES["ru"]
OWN = "Bu qism muallifning o'zi tomonidan yozilgan, unda hech qanday boshqa manbadan olingan jumla yo'q va u faqat shu ish uchun tayyorlangan. " * 3


@pytest.fixture
def settings():
    return config.get_settings()


def _mock_http(monkeypatch, handler):
    real = httpx.Client

    def factory(*a, **k):
        k.pop("transport", None)
        return real(*a, transport=httpx.MockTransport(handler), **k)

    for mod in ("app.plagiarism.online.httpx.Client", "app.plagiarism.web.httpx.Client", "app.plagiarism.harvest.base.httpx.Client"):
        monkeypatch.setattr(mod, factory)
    monkeypatch.setattr(web, "is_public_url", lambda u: True)


def _inverted(text: str) -> dict:
    inv: dict = {}
    for i, w in enumerate(text.split()):
        inv.setdefault(w, []).append(i)
    return inv


def _check(client, name, data, modules):
    item = upload(client, name, data, modules=",".join(modules), keep_for_similarity="false")
    aid = item["analysis"]["id"]
    return aid, client.get(f"/api/analyses/{aid}").json()


# ---------------------------------------------------------------- registry & estimates
def test_modules_endpoint_lists_all_with_availability_and_estimate(user_client):
    r = user_client.get("/api/corpus/modules", params={"words": 29205}).json()
    mods = {m["key"]: m for m in r["modules"]}
    assert set(mods) == {"corpus", "own", "ojs", "scholarly", "cyberleninka", "patents", "legal", "web", "translation", "templates"}
    assert not mods["web"]["available"] and "BRAVE" in mods["web"]["reason"]
    assert not mods["patents"]["available"] and "LENS" in mods["patents"]["reason"]
    assert not mods["translation"]["available"]  # tests run with hash vectors: translation needs the multilingual model
    sch = mods["scholarly"]
    assert sch["available"] and sch["queries"] == 30 and sch["cost_usd"] == 0 and sch["requests"] == 30 * len(sch["sources"])
    assert "core" not in sch["sources"]  # CORE needs a free API key


def test_online_modules_wait_for_confirmation_with_per_module_estimate(user_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "BRAVE_API_KEY", SecretStr("k"))
    _, a = _check(user_client, "est.docx", make_docx([OWN, UZ["human"][1]]), ["corpus", "scholarly", "legal", "web", "templates"])
    assert a["status"] == "awaiting_confirmation"
    est = a["web_estimate"]
    assert est["modules"]["scholarly"]["cost_usd"] == 0 and est["modules"]["scholarly"]["requests"] > 0
    assert est["modules"]["web"]["cost_usd"] > 0 and est["modules"]["legal"]["cost_usd"] > 0
    assert est["total_cost_usd"] == pytest.approx(est["modules"]["web"]["cost_usd"] + est["modules"]["legal"]["cost_usd"])
    assert a["check_modules"] == ["corpus", "scholarly", "legal", "web", "templates"]


def test_local_only_modules_start_immediately(user_client):
    _, a = _check(user_client, "local.docx", make_docx([OWN]), ["corpus", "own", "templates"])
    assert a["status"] == "completed"


# ---------------------------------------------------------------- scholarly databases
def test_scholarly_module_compares_abstracts_and_open_fulltexts(user_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "CORE_API_KEY", SecretStr("core-key"))
    abstract, pdf_text, arxiv_text = UZ["human"][1], UZ["human"][2], UZ["human"][3]
    calls: dict[str, int] = {}

    def handler(req: httpx.Request):
        host = req.url.host
        calls[host] = calls.get(host, 0) + 1
        if host == "api.openalex.org":
            return httpx.Response(200, json={"results": [
                {"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1/abc", "title": "OpenAlex maqolasi", "publication_year": 2021,
                 "abstract_inverted_index": _inverted(abstract), "authorships": [{"author": {"display_name": "Karimov A."}}],
                 "best_oa_location": {"pdf_url": "https://repo.example.org/open.pdf", "license": "cc-by"}},
                {"id": "https://openalex.org/W2", "doi": None, "title": "Yopiq maqola", "abstract_inverted_index": None,
                 "best_oa_location": {"pdf_url": "https://publisher.example.org/closed.pdf", "license": None}},
            ]})
        if host == "api.crossref.org":
            return httpx.Response(200, json={"message": {"items": [{"DOI": "10.2/x", "title": ["Crossref"], "abstract": "<jats:p>boshqa mavzu</jats:p>"}]}})
        if host == "api.semanticscholar.org":
            return httpx.Response(200, json={"data": []})
        if host == "api.core.ac.uk":
            assert req.headers["authorization"] == "Bearer core-key"
            return httpx.Response(200, json={"results": []})
        if host == "export.arxiv.org" and req.url.path == "/api/query":
            xml = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2101.00001v1</id><title>Arxiv paper</title>'
                   f"<summary>{arxiv_text}</summary><published>2021-01-01T00:00:00Z</published><author><name>Doe J.</name></author>"
                   '<link title="pdf" href="http://arxiv.org/pdf/2101.00001v1"/></entry></feed>')
            return httpx.Response(200, content=xml.encode())
        if req.url.path == "/open.pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=_pdf_bytes(pdf_text))
        if req.url.path.startswith("/pdf/"):
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=_pdf_bytes("unrelated arxiv body " * 40))
        if req.url.path == "/closed.pdf":
            raise AssertionError("closed-licence full text must not be downloaded")
        return httpx.Response(404)

    _mock_http(monkeypatch, handler)
    aid, a = _check(user_client, "sch.docx", make_docx([OWN, abstract, pdf_text, arxiv_text]), ["scholarly", "templates"])
    assert a["status"] == "awaiting_confirmation"
    user_client.post(f"/api/analyses/{aid}/confirm", json={"modules": ["scholarly", "templates"]})
    pl = user_client.get(f"/api/analyses/{aid}/plagiarism").json()
    srcs = [s for s in pl["sources"] if s["module"] == "scholarly"]
    urls = {s["url"] for s in srcs}
    assert "https://doi.org/10.1/abc" in urls and "http://arxiv.org/abs/2101.00001v1" in urls
    oa = next(s for s in srcs if s["url"] == "https://doi.org/10.1/abc")
    assert oa["authors"] == "Karimov A." and oa["share_text"] > 30  # abstract + open PDF
    st = pl["modules"]["online_stats"]["scholarly"]
    assert set(st["per_source"]) == {"openalex", "crossref", "semanticscholar", "core", "arxiv"}
    assert any(p["url"] == "https://repo.example.org/open.pdf" and p["status"] == "ok" for p in st["pages"])
    checks = {c["key"]: c for c in pl["modules"]["checks"]}
    assert checks["scholarly"]["state"] == "checked" and checks["scholarly"]["sources_found"] >= 2
    assert checks["web"]["state"] == "off" and pl["modules"]["checked_count"] == 2 and pl["modules"]["module_total"] == 10
    import pymupdf

    pdf = user_client.get(f"/api/analyses/{aid}/report", params={"kind": "plagiarism"})
    text = "".join(pg.get_text() for pg in pymupdf.open(stream=pdf.content, filetype="pdf"))
    assert "10 ta moduldan 2 tasida tekshirilgan" in text and "Ilmiy bazalar" in text and "o'chirilgan" in text


def test_failing_api_does_not_stop_other_sources(user_client, monkeypatch):
    def handler(req):
        if req.url.host == "api.openalex.org":
            return httpx.Response(200, json={"results": [{"id": "https://openalex.org/W9", "title": "T", "abstract_inverted_index": _inverted(UZ["human"][1])}]})
        return httpx.Response(503)

    _mock_http(monkeypatch, handler)
    aid, _ = _check(user_client, "fail.docx", make_docx([OWN, UZ["human"][1]]), ["scholarly"])
    user_client.post(f"/api/analyses/{aid}/confirm", json={"modules": ["scholarly"]})
    pl = user_client.get(f"/api/analyses/{aid}/plagiarism").json()
    assert [s["module"] for s in pl["sources"]] == ["scholarly"]
    st = pl["modules"]["online_stats"]["scholarly"]
    assert st["per_source"]["crossref"]["errors"] >= 1 and any("crossref: http_503" in e for e in st["errors"])


# ---------------------------------------------------------------- CyberLeninka, patents, lex.uz
def test_cyberleninka_module(user_client, monkeypatch):
    ru = RU["human"]

    def handler(req):
        if req.url.path == "/api/search":
            return httpx.Response(200, json={"articles": [{"name": "<b>Статья</b>", "annotation": ru[0], "link": "/article/n/test", "authors": ["Иванов И."], "year": 2019}]})
        if req.url.path == "/article/n/test/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=_pdf_bytes(ru[1] + " " + ru[2]))
        return httpx.Response(404)

    _mock_http(monkeypatch, handler)
    aid, _ = _check(user_client, "cl.docx", make_docx(["Собственный текст автора, написанный специально для этой работы и нигде не опубликованный. " * 3, ru[0], ru[2]]),
                    ["cyberleninka"])
    user_client.post(f"/api/analyses/{aid}/confirm", json={"modules": ["cyberleninka"]})
    pl = user_client.get(f"/api/analyses/{aid}/plagiarism").json()
    src = next(s for s in pl["sources"] if s["module"] == "cyberleninka")
    assert src["url"] == "https://cyberleninka.ru/article/n/test" and src["title"] == "Статья" and src["share_text"] > 40


def test_patent_module_uses_lens_api(user_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "LENS_API_TOKEN", SecretStr("lens-token"))
    claim = UZ["human"][2]

    def handler(req):
        assert req.url.host == "api.lens.org" and req.headers["authorization"] == "Bearer lens-token"
        return httpx.Response(200, json={"data": [{"lens_id": "001-002-003", "biblio": {"invention_title": [{"text": "Qurilma"}]},
                                                    "abstract": [{"text": "Qisqa annotatsiya."}], "claims": [{"claims": [{"claim_text": [claim]}]}],
                                                    "date_published": "2020-05-01"}]})

    _mock_http(monkeypatch, handler)
    aid, a = _check(user_client, "pat.docx", make_docx([OWN, claim]), ["patents"])
    assert a["web_estimate"]["modules"]["patents"]["available"]
    user_client.post(f"/api/analyses/{aid}/confirm", json={"modules": ["patents"]})
    src = next(s for s in user_client.get(f"/api/analyses/{aid}/plagiarism").json()["sources"] if s["module"] == "patents")
    assert src["url"] == "https://www.lens.org/lens/patent/001-002-003" and src["title"] == "Qurilma" and src["year"] == 2020


def test_legal_module_searches_only_lex_uz(user_client, settings, monkeypatch):
    monkeypatch.setattr(settings, "BRAVE_API_KEY", SecretStr("k"))
    law = UZ["human"][3]
    queries = []

    class Brave:
        def __init__(self, *a, **k):
            pass

        def search(self, q):
            queries.append(q)
            return [{"url": "https://lex.uz/docs/123456", "title": "Qonun"}, {"url": "https://other.example.org/copy", "title": "Boshqa"}]

    class Fetch:
        def __init__(self, *a, **k):
            pass

        def fetch_text(self, url):
            assert "lex.uz" in url, "only lex.uz pages are fetched by the legal module"
            return "Qonun", law

    monkeypatch.setattr(web, "BraveClient", Brave)
    monkeypatch.setattr(web, "Fetcher", Fetch)
    aid, _ = _check(user_client, "law.docx", make_docx([OWN, law]), ["legal"])
    user_client.post(f"/api/analyses/{aid}/confirm", json={"modules": ["legal"]})
    pl = user_client.get(f"/api/analyses/{aid}/plagiarism").json()
    assert queries and all(q.startswith("site:lex.uz ") for q in queries)
    assert [s["url"] for s in pl["sources"]] == ["https://lex.uz/docs/123456"] and pl["sources"][0]["module"] == "legal"


# ---------------------------------------------------------------- OJS module, templates
def test_ojs_articles_form_their_own_module(user_client):
    with SessionLocal() as db:
        corpus.ingest(db, UZ["human"][:3], {"title": "OJS maqola", "source_type": "ojs", "source_url": "https://j.example.uz/article/view/1"})
    data = make_docx([OWN, UZ["human"][1]])
    _, a = _check(user_client, "ojs1.docx", data, ["corpus", "ojs"])
    pl = user_client.get(f"/api/analyses/{a['id']}/plagiarism").json()
    assert [s["module"] for s in pl["sources"]] == ["ojs"]
    _, a2 = _check(user_client, "ojs2.docx", data, ["corpus"])
    assert user_client.get(f"/api/analyses/{a2['id']}/plagiarism").json()["sources"] == []


def test_template_phrases_are_not_borrowing(user_client):
    tpl = ("Mavzuning dolzarbligi shundaki, ushbu ishda tadqiqotning maqsadi va tadqiqotning vazifalari belgilangan. "
           "Shuni ta'kidlash kerakki, bugungi kunda bu masala muhim ahamiyat kasb etadi. ")
    with SessionLocal() as db:
        corpus.ingest(db, [tpl + UZ["human"][1], UZ["human"][3]], {"title": "Manba"})
    data = make_docx([OWN, tpl + UZ["human"][1]])
    _, on = _check(user_client, "t1.docx", data, ["corpus", "templates"])
    _, off = _check(user_client, "t2.docx", data, ["corpus"])
    p_on = user_client.get(f"/api/analyses/{on['id']}/plagiarism").json()
    p_off = user_client.get(f"/api/analyses/{off['id']}/plagiarism").json()
    assert p_on["modules"]["templates"]["excluded_from_borrowing"] >= 15
    assert p_on["borrowing"] < p_off["borrowing"] - 5


# ---------------------------------------------------------------- translation (cross-language)
class DictBackend:
    """A stand-in multilingual model: maps Russian words to their Uzbek counterparts, then bag-of-words."""

    id, dims = "dict-model", 256

    def __init__(self, mapping):
        self.mapping = mapping

    def encode(self, texts):
        out = np.zeros((len(texts), self.dims), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in t.lower().split():
                w = self.mapping.get(w.strip(".,;:()«»"), w.strip(".,;:()«»"))
                out[i, hash(w) % self.dims] += 1
        n = np.linalg.norm(out, axis=1, keepdims=True)
        n[n == 0] = 1
        return out / n


def test_translated_borrowing_is_found_only_with_translation_module(user_client, monkeypatch):
    from app.plagiarism.textnorm import display_text, tokenize

    def words(text):
        d = display_text(text)
        return [d[t.start : t.end] for t in tokenize(d)]

    ru_words = words(RU["human"][0] + " " + RU["human"][1])
    uz_words = words(" ".join(UZ["human"]))[: len(ru_words)]
    mapping = {r.lower().strip(".,;:()«»"): u.lower().strip(".,;:()«»") for r, u in zip(ru_words, uz_words)}
    be = DictBackend(mapping)
    monkeypatch.setattr(embeddings, "get_backend", lambda: be)
    monkeypatch.setattr(embeddings, "expected_kind", lambda: "model2vec")
    corpus.vector_index.invalidate()
    with SessionLocal() as db:
        ref = corpus.ingest(db, [RU["human"][0], RU["human"][1]], {"title": "Русский источник"})
        assert ref.language == "ru"
    corpus.vector_index.invalidate()
    translated = " ".join(uz_words)  # the Uzbek "translation" of the Russian source
    data = make_docx([OWN, translated])
    _, on = _check(user_client, "tr1.docx", data, ["corpus", "translation"])
    p_on = user_client.get(f"/api/analyses/{on['id']}/plagiarism").json()
    assert p_on["sources"], p_on["modules"]["paraphrase"]
    src = p_on["sources"][0]
    assert src["title"] == "Русский источник" and src["translation_words"] > 40
    assert any(s[4] == "t" for s in p_on["spans"]) and p_on["modules"]["translation_share"] > 20
    assert next(c for c in p_on["modules"]["checks"] if c["key"] == "translation")["sources_found"] == 1
    _, off = _check(user_client, "tr2.docx", data, ["corpus"])
    assert user_client.get(f"/api/analyses/{off['id']}/plagiarism").json()["sources"] == []


# ---------------------------------------------------------------- bulk corpus import
def test_zip_upload_imports_many_documents_with_folders(admin):  # noqa: F811 - fixture
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for i in range(3):
            z.writestr(f"Darsliklar/{i}-bob/kitob{i}.docx", make_docx([UZ["human"][i], UZ["human"][i + 1]]))
        z.writestr("__MACOSX/._kitob.docx", b"junk")
        z.writestr("readme.exe", b"MZ")
    r = admin.post("/api/corpus/upload-zip", files={"file": ("kutubxona.zip", buf.getvalue(), "application/zip")}, data={"doc_kind": "textbook"})
    assert r.status_code == 201, r.text
    job = r.json()["job"]
    assert job["total"] == 3 and job["added"] == 3
    with SessionLocal() as db:
        folders = {d.folder for d in db.query(RefDocument).all()}
    assert "Darsliklar/0-bob" in folders


def test_local_folder_import(admin, settings, monkeypatch, tmp_path):  # noqa: F811 - fixture
    root = tmp_path / "Kutubxona"
    (root / "Maqolalar").mkdir(parents=True)
    texts = UZ["human"] + RU["human"]
    for i in range(4):
        (root / "Maqolalar" / f"m{i}.docx").write_bytes(make_docx([texts[2 * i], texts[2 * i + 1]]))
    (root / "rasm.png").write_bytes(b"\x89PNG")
    monkeypatch.setattr(settings, "CORPUS_LOCAL_IMPORT", False)
    assert admin.post("/api/corpus/import-folder", json={"path": str(root)}).status_code == 403
    monkeypatch.setattr(settings, "CORPUS_LOCAL_IMPORT", True)
    r = admin.post("/api/corpus/import-folder", json={"path": str(root), "doc_kind": "article"})
    assert r.status_code == 201, r.text
    assert r.json()["job"]["added"] == 4
    assert all((root / "Maqolalar" / f"m{i}.docx").exists() for i in range(4))  # originals are left untouched
    assert admin.post("/api/corpus/import-folder", json={"path": str(root / "yoq")}).status_code == 422


def test_ojs_auto_harvest_is_scheduled_and_skips_known_articles(settings, monkeypatch):
    from app.plagiarism import jobs

    galley_requests = []
    oai = ('<?xml version="1.0"?><OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords><record><header><identifier>oai:1</identifier></header>'
           '<metadata><oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
           f'<dc:title>Jurnal maqolasi</dc:title><dc:description>{UZ["human"][0]} {UZ["human"][1]}</dc:description>'
           '<dc:identifier>https://j.example.uz/index.php/j/article/view/7</dc:identifier><dc:date>2022</dc:date></oai_dc:dc></metadata></record></ListRecords></OAI-PMH>')

    def handler(req):
        if req.url.path.endswith("/oai"):
            return httpx.Response(200, content=oai.encode())
        if "/article/view/" in req.url.path:
            galley_requests.append(str(req.url))
            return httpx.Response(200, text="<html>no galley</html>")
        return httpx.Response(404)

    _mock_http(monkeypatch, handler)
    monkeypatch.setattr(settings, "HARVEST_OJS_URLS", "https://j.example.uz/index.php/j")
    monkeypatch.setattr(settings, "OJS_AUTO_HARVEST_HOURS", 24)
    with SessionLocal() as db:
        db.query(CorpusJob).delete()
        db.commit()
    first = jobs.schedule_ojs_harvest()
    assert first and jobs.schedule_ojs_harvest() is None  # not again within 24 hours
    with SessionLocal() as db:
        assert db.get(CorpusJob, first).added == 1
        assert db.query(RefDocument).filter(RefDocument.source_type == "ojs").count() == 1
    from datetime import UTC, datetime, timedelta

    galley_requests.clear()
    again = jobs.schedule_ojs_harvest(now=datetime.now(UTC) + timedelta(hours=25))
    with SessionLocal() as db:
        assert db.get(CorpusJob, again).skipped == 1
    assert galley_requests == []  # a known article is skipped before its page is downloaded


def test_reanalysis_keeps_module_selection(user_client):
    aid, a = _check(user_client, "re.docx", make_docx([OWN]), ["corpus", "templates"])
    r = user_client.post(f"/api/documents/{a['document_id']}/analyses", json={"depth": "quick"})
    assert r.status_code == 201 and r.json()["check_modules"] == ["corpus", "templates"]


def test_module_with_no_successful_request_is_reported_as_error(user_client, monkeypatch):
    def handler(req):
        raise httpx.ConnectError("offline")

    _mock_http(monkeypatch, handler)
    aid, _ = _check(user_client, "off.docx", make_docx([OWN, UZ["human"][1]]), ["corpus", "cyberleninka"])
    user_client.post(f"/api/analyses/{aid}/confirm", json={"modules": ["corpus", "cyberleninka"]})
    mods = user_client.get(f"/api/analyses/{aid}/plagiarism").json()["modules"]
    c = next(c for c in mods["checks"] if c["key"] == "cyberleninka")
    assert c["state"] == "error" and "connection_error" in c["errors"][0]
    assert mods["checked_count"] == 1  # only the reference corpus really checked the text
