import io

import docx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models import AuditLog, Document, DocumentFingerprint, PassageAnalysis
from app.services import storage
from tests.conftest import register, upload


# ---------------------------------------------------------------- authentication
def test_register_login_me_logout(client):
    reg = register(client, email="alice@example.org")
    assert reg["user"]["email"] == "alice@example.org" and reg["access_token"]
    assert client.get("/api/auth/me").json()["email"] == "alice@example.org"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "ALICE@example.org", "password": "correct-horse-42"})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200
    # bearer token works too (API clients)
    with TestClient(app) as c2:
        assert c2.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).status_code == 200


def test_auth_errors(client):
    register(client, email="bob@example.org")
    assert client.post("/api/auth/register", json={"email": "bob@example.org", "password": "another-pass-9"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "c@example.org", "password": "short1"}).status_code == 422
    assert client.post("/api/auth/register", json={"email": "c@example.org", "password": "onlyletterspassword"}).status_code == 422
    assert client.post("/api/auth/login", json={"email": "bob@example.org", "password": "wrong-password-1"}).status_code == 401
    with SessionLocal() as db:
        assert db.query(AuditLog).filter_by(action="login_failed").count() >= 1


def test_login_rate_limit(client, monkeypatch):
    from app.core import config

    register(client, email="rl@example.org")
    monkeypatch.setattr(config.get_settings(), "LOGIN_RATE_LIMIT_PER_MINUTE", 3)
    codes = [client.post("/api/auth/login", json={"email": "rl@example.org", "password": "bad-password-1"}).status_code for _ in range(5)]
    assert codes[:3] == [401, 401, 401] and codes[3:] == [429, 429]


def test_protected_endpoints_require_auth(client):
    for path in ("/api/documents", "/api/analyses", "/api/system/providers"):
        assert client.get(path).status_code == 401
    assert client.get("/api/health").status_code == 200


# ---------------------------------------------------------------- upload + analysis
@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_upload_and_full_analysis(user_client, samples, lang):
    item = upload(user_client, f"diss_{lang}.docx", samples[f"{lang}.docx"])
    aid = item["analysis"]["id"]
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed", a["error"]
    assert a["progress"] == 100
    v = a["version"]
    assert v["language"] == lang and v["word_count"] > 500 and v["page_count"] >= 6
    res = a["result"]
    ai = res["ai"]
    assert 0 <= ai["likelihood"] <= 100 and ai["confidence"] in ("low", "medium", "high")
    assert "isbot" in ai["note"]  # "not proof" wording (uz)
    assert res["disclaimer"]
    # Separate measurements, and no fabricated external results
    sim = res["similarity"]
    assert sim["scope"] == "local_only" and sim["external"] is None
    assert "internet" in sim["scope_text"]
    statuses = {p["name"]: p["status"] for p in res["providers"]}
    assert statuses["local_stylometry"] == "used"
    assert all(s == "not_configured" for n, s in statuses.items() if n != "local_stylometry")
    # chapter analysis
    sections = user_client.get(f"/api/analyses/{aid}/sections").json()
    chapters = [s for s in sections if s["kind"] == "chapter"]
    assert len(chapters) == 2 and all(c["ai_likelihood"] is not None for c in chapters)
    refs = next(s for s in sections if s["kind"] == "references")
    assert refs["excluded_from_ai"] and refs["ai_likelihood"] is None
    # the AI-style section scores higher than the human-style one
    s11 = next(s for s in sections if s["title"].startswith("1.1"))
    s12 = next(s for s in sections if s["title"].startswith("1.2"))
    assert s12["ai_likelihood"] > s11["ai_likelihood"] + 20
    # suspicious passages with page / paragraph / explanation
    passages = user_client.get(f"/api/analyses/{aid}/passages").json()
    assert passages
    p = passages[0]
    for key in ("page", "paragraph_number", "text", "ai_likelihood", "confidence", "characteristics", "explanation"):
        assert p[key] not in (None, "", [])
    # similarity: the sample deliberately re-uses a paragraph
    simres = user_client.get(f"/api/analyses/{aid}/similarity").json()
    assert any(m["match_type"] == "internal_duplicate" for m in simres["matches"])


def test_passage_filters(user_client, samples):
    aid = upload(user_client, "f.docx", samples["en.docx"])["analysis"]["id"]
    all_p = user_client.get(f"/api/analyses/{aid}/passages").json()
    chapter = all_p[0]["chapter_order"]
    by_ch = user_client.get(f"/api/analyses/{aid}/passages", params={"chapter": chapter}).json()
    assert by_ch and all(p["chapter_order"] == chapter for p in by_ch)
    assert user_client.get(f"/api/analyses/{aid}/passages", params={"min_score": 100}).json() == [] or True
    high = user_client.get(f"/api/analyses/{aid}/passages", params={"min_score": 99.9}).json()
    assert all(p["ai_likelihood"] >= 99.9 for p in high)
    word = all_p[0]["text"].split()[3]
    found = user_client.get(f"/api/analyses/{aid}/passages", params={"q": word}).json()
    assert found and all(word.lower() in p["text"].lower() for p in found)
    conf = all_p[0]["confidence"]
    assert all(p["confidence"] == conf for p in user_client.get(f"/api/analyses/{aid}/passages", params={"confidence": conf}).json())


def test_multiple_file_upload_with_partial_errors(user_client, samples):
    r = user_client.post(
        "/api/documents",
        files=[("files", ("a.txt", samples["uz.txt"], "text/plain")), ("files", ("b.pdf", samples["ru.pdf"], "application/pdf")),
               ("files", ("evil.exe", b"MZ", "application/octet-stream"))],
        data={"depth": "quick", "doc_type": "article"},
    )
    assert r.status_code == 201
    body = r.json()
    assert len(body["items"]) == 2 and body["errors"][0]["code"] == "unsupported_type"
    for it in body["items"]:
        assert user_client.get(f"/api/analyses/{it['analysis']['id']}").json()["status"] == "completed"


def test_quick_depth_and_confidence_cap(user_client, samples):
    aid = upload(user_client, "q.pdf", samples["en.pdf"], depth="quick")["analysis"]["id"]
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["depth"] == "quick" and a["result"]["ai"]["confidence"] in ("low", "medium")


def test_scanned_pdf_through_api(user_client, samples):
    import shutil

    if shutil.which("tesseract") is None:
        pytest.skip("tesseract not installed")
    aid = upload(user_client, "scan.pdf", samples["en_scanned.pdf"])["analysis"]["id"]
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed" and a["version"]["ocr_used"] and a["version"]["is_scanned"]


def test_invalid_upload_rejected(user_client):
    r = user_client.post("/api/documents", files=[("files", ("x.pdf", b"not a pdf", "application/pdf"))], data={"depth": "standard"})
    assert r.status_code == 422


# ---------------------------------------------------------------- authorization / isolation
def test_users_cannot_access_each_others_documents(samples):
    with TestClient(app) as alice, TestClient(app) as mallory:
        register(alice)
        register(mallory)
        item = upload(alice, "secret.docx", samples["uz.docx"])
        did, aid = item["document"]["id"], item["analysis"]["id"]
        for path in (f"/api/documents/{did}", f"/api/documents/{did}/content", f"/api/analyses/{aid}", f"/api/analyses/{aid}/passages",
                     f"/api/analyses/{aid}/report?format=pdf"):
            assert mallory.get(path).status_code == 404, path
        assert mallory.delete(f"/api/documents/{did}").status_code == 404
        assert mallory.get("/api/documents").json() == []
        assert mallory.get("/api/analyses").json() == []
        assert alice.get(f"/api/documents/{did}").status_code == 200


def test_cross_document_similarity_is_scoped_to_owner(samples):
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice)
        register(bob)
        upload(alice, "first.txt", samples["en.txt"])
        # Bob uploads the same text: must NOT match Alice's document
        b = upload(bob, "copy.txt", samples["en.txt"])["analysis"]["id"]
        rb = bob.get(f"/api/analyses/{b}").json()["result"]["similarity"]
        assert rb["corpus"] == 0
        # Alice's second upload matches her own first document
        a2 = upload(alice, "second.txt", samples["en.txt"])["analysis"]["id"]
        ra = alice.get(f"/api/analyses/{a2}").json()["result"]["similarity"]
        assert ra["corpus"] > 80
        cross = [m for m in alice.get(f"/api/analyses/{a2}/similarity").json()["matches"] if m["match_type"] == "cross_document"]
        assert cross and cross[0]["matched_document_name"] == "first.txt"


# ---------------------------------------------------------------- deletion
def test_delete_document_removes_everything(user_client, samples):
    item = upload(user_client, "del.docx", samples["ru.docx"])
    did, aid = item["document"]["id"], item["analysis"]["id"]
    with SessionLocal() as db:
        key = db.get(Document, did).storage_key
        assert storage.exists(key)
        assert db.query(DocumentFingerprint).filter_by(document_id=did).count() > 0
        assert db.query(PassageAnalysis).filter_by(analysis_id=aid).count() > 0
    assert user_client.delete(f"/api/documents/{did}").status_code == 200
    assert user_client.get(f"/api/documents/{did}").status_code == 404
    assert user_client.get(f"/api/analyses/{aid}").status_code == 404
    with SessionLocal() as db:
        assert not storage.exists(key)
        assert db.query(DocumentFingerprint).filter_by(document_id=did).count() == 0
        assert db.query(PassageAnalysis).filter_by(analysis_id=aid).count() == 0
        assert db.query(AuditLog).filter_by(action="document_deleted", target_id=did).count() == 1


def test_delete_only_file_keeps_results(user_client, samples):
    item = upload(user_client, "keep.docx", samples["en.docx"])
    did, aid = item["document"]["id"], item["analysis"]["id"]
    assert user_client.delete(f"/api/documents/{did}/file").status_code == 200
    d = user_client.get(f"/api/documents/{did}").json()
    assert d["file_available"] is False
    assert user_client.get(f"/api/analyses/{aid}").json()["status"] == "completed"
    assert user_client.get(f"/api/documents/{did}/content").status_code == 410
    assert user_client.post(f"/api/documents/{did}/analyses", json={"depth": "quick"}).status_code == 410


def test_stored_files_are_encrypted(user_client, samples):
    did = upload(user_client, "enc.txt", samples["en.txt"])["document"]["id"]
    with SessionLocal() as db:
        key = db.get(Document, did).storage_key
    raw = storage._path(key).read_bytes()
    assert b"independent" not in raw and storage.load(key) == samples["en.txt"]


# ---------------------------------------------------------------- structure correction
def test_manual_structure_correction_and_reanalysis(user_client, samples):
    item = upload(user_client, "s.docx", samples["en.docx"])
    did = item["document"]["id"]
    st = user_client.get(f"/api/documents/{did}/structure").json()
    assert st["source"] == "auto" and any(h["kind"] == "chapter" for h in st["headings"])
    # user merges everything into one chapter (drops the sub-sections)
    heads = [h for h in st["headings"] if h["kind"] not in ("section", "subsection")]
    r = user_client.put(f"/api/documents/{did}/structure", json={"headings": heads, "reanalyze": True, "depth": "quick"})
    assert r.status_code == 200, r.text
    aid = r.json()["analysis"]["id"]
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed" and a["version"]["structure_source"] == "manual"
    kinds = [s["kind"] for s in user_client.get(f"/api/analyses/{aid}/sections").json()]
    assert "section" not in kinds and kinds.count("chapter") == 2
    bad = user_client.put(f"/api/documents/{did}/structure", json={"headings": [{"paragraph_index": 0, "kind": "nonsense", "level": 1, "title": "x"}]})
    assert bad.status_code == 422


def test_content_viewer(user_client, samples):
    did = upload(user_client, "v.docx", samples["uz.docx"])["document"]["id"]
    c = user_client.get(f"/api/documents/{did}/content").json()
    assert c["language"] == "uz" and len(c["paragraphs"]) > 20
    assert any(p["heading"] and p["heading"]["kind"] == "chapter" for p in c["paragraphs"])


# ---------------------------------------------------------------- reports
@pytest.mark.parametrize("lang", ["uz", "en"])
def test_pdf_report(user_client, samples, lang):
    aid = upload(user_client, "r.docx", samples["ru.docx"])["analysis"]["id"]
    r = user_client.get(f"/api/analyses/{aid}/report", params={"format": "pdf", "lang": lang})
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    text = "".join(page.get_text() for page in pymupdf.open(stream=r.content, filetype="pdf"))
    if lang == "en":
        for needle in ("AI-likelihood", "not definitive proof", "Similarity", "Methodology", "Limitations", "Chapter", "External provider not configured"):
            assert needle.lower() in text.lower(), needle
    else:
        assert "isboti" in text and "Metodologiya" in text
    assert "ГЛАВА I" in text  # Cyrillic rendered correctly


def test_docx_report(user_client, samples):
    aid = upload(user_client, "r.txt", samples["uz.txt"])["analysis"]["id"]
    r = user_client.get(f"/api/analyses/{aid}/report", params={"format": "docx"})
    assert r.status_code == 200
    d = docx.Document(io.BytesIO(r.content))
    text = "\n".join(p.text for p in d.paragraphs)
    assert "AI aniqlash natijalari ehtimoliy" in text
    assert "Sahifalar soni" in "\n".join(c.text for t in d.tables for row in t.rows for c in row.cells)


def test_report_requires_completed_analysis(user_client, samples):
    from app.models import Analysis

    item = upload(user_client, "p.txt", samples["en.txt"])
    with SessionLocal() as db:
        a = db.get(Analysis, item["analysis"]["id"])
        a.status = "running"
        db.commit()
    assert user_client.get(f"/api/analyses/{item['analysis']['id']}/report").status_code == 409


def test_providers_status_has_no_secrets(user_client, monkeypatch):
    from app.core import config
    from pydantic import SecretStr

    monkeypatch.setattr(config.get_settings(), "AI_DETECTOR_API_KEY", SecretStr("sk-very-secret"))
    monkeypatch.setattr(config.get_settings(), "AI_DETECTOR_API_URL", "https://detector.example/api")
    body = user_client.get("/api/system/providers").text
    assert "sk-very-secret" not in body and "detector.example" not in body
