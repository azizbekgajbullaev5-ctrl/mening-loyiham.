"""Local (no-Docker) mode: checkpoints/resume, retries, queue, bundled UI, launcher."""
import importlib.util
import shutil
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.core import config
from app.core.database import SessionLocal, engine
from app.models import Analysis, Document
from app.services import checkpoints, pipeline, storage
from tests.conftest import upload

ROOT = Path(__file__).resolve().parents[2]


def test_resume_after_crash_reuses_extraction_checkpoint(user_client, samples, monkeypatch):
    real_academic = pipeline.analyze_academic

    def crash(*a, **k):
        raise RuntimeError("simulated crash late in the pipeline")

    monkeypatch.setattr(pipeline, "analyze_academic", crash)
    item = upload(user_client, "crash.docx", samples["en.docx"])
    aid, did = item["analysis"]["id"], item["document"]["id"]
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "failed" and a["error"].startswith("internal_error")
    with SessionLocal() as db:
        d = db.get(Document, did)
        assert checkpoints.load(d.id, d.sha256, "extract") is not None

    # resume: extraction must NOT run again, the saved checkpoint is used
    def no_extract(*a, **k):
        raise AssertionError("extraction should have been restored from the checkpoint")

    monkeypatch.setattr(pipeline, "extract", no_extract)
    monkeypatch.setattr(pipeline, "analyze_academic", real_academic)
    r = user_client.post(f"/api/analyses/{aid}/resume")
    assert r.status_code == 200, r.text
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed" and a["attempts"] == 2
    assert a["result"]["ai"]["passages_analyzed"] > 0
    # resuming a completed analysis is refused
    assert user_client.post(f"/api/analyses/{aid}/resume").status_code == 409


def test_checkpoints_removed_with_document(user_client, samples):
    item = upload(user_client, "ck.txt", samples["en.txt"])
    did = item["document"]["id"]
    with SessionLocal() as db:
        d = db.get(Document, did)
        sha = d.sha256
    assert checkpoints.load(did, sha, "extract") is not None
    user_client.delete(f"/api/documents/{did}")
    assert checkpoints.load(did, sha, "extract") is None


def test_automatic_retry(user_client, samples, monkeypatch):
    monkeypatch.setattr(config.get_settings(), "AUTO_RETRY_ATTEMPTS", 1)
    monkeypatch.setattr("app.tasks.queue.time.sleep", lambda s: None)
    real = pipeline.analyze_academic
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return real(*a, **k)

    monkeypatch.setattr(pipeline, "analyze_academic", flaky)
    aid = upload(user_client, "retry.txt", samples["ru.txt"])["analysis"]["id"]
    a = user_client.get(f"/api/analyses/{aid}").json()
    assert a["status"] == "completed" and a["attempts"] == 2


def test_permanent_error_is_not_retried(user_client, samples, monkeypatch):
    monkeypatch.setattr(config.get_settings(), "AUTO_RETRY_ATTEMPTS", 2)
    item = upload(user_client, "gone.txt", samples["uz.txt"])
    did = item["document"]["id"]
    with SessionLocal() as db:
        d = db.get(Document, did)
        storage.delete(d.storage_key)
        checkpoints.delete_document(d.id)
    r = user_client.post(f"/api/documents/{did}/analyses", json={"depth": "quick"})
    a = user_client.get(f"/api/analyses/{r.json()['id']}").json()
    assert a["status"] == "failed" and a["error"].startswith("file_unavailable") and a["attempts"] == 1


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_ocr_resumes_from_saved_pages(samples, monkeypatch):
    from app.document_processing import extractors

    ocr_calls = []
    real_ocr = extractors._ocr_page
    monkeypatch.setattr(extractors, "_ocr_page", lambda page, dpi, langs: ocr_calls.append(page.number) or real_ocr(page, dpi, langs))
    saved = {}
    doc = extractors.extract("pdf", samples["en_scanned.pdf"], ocr_cache={"0": "CACHED PAGE ONE TEXT from an earlier run."},
                             on_ocr_page=lambda p, t: saved.__setitem__(p, t))
    assert ocr_calls == [1]  # page 0 came from the cache
    assert "CACHED PAGE ONE TEXT" in doc.blocks[0].text and 1 in saved


def test_queue_position(user_client, samples):
    items = [upload(user_client, f"q{i}.txt", samples["en.txt"], depth="quick") for i in range(3)]
    ids = [it["analysis"]["id"] for it in items]
    with SessionLocal() as db:
        for aid in ids:
            db.get(Analysis, aid).status = "queued"
        db.commit()
    positions = [user_client.get(f"/api/analyses/{aid}").json()["queue_position"] for aid in ids]
    assert positions == sorted(positions) and positions[0] >= 1 and len(set(positions)) == 3
    with SessionLocal() as db:
        for aid in ids:
            db.get(Analysis, aid).status = "completed"
        db.commit()
    assert user_client.get(f"/api/analyses/{ids[0]}").json()["queue_position"] is None


def test_single_worker_by_default():
    assert config.get_settings().MAX_CONCURRENT_ANALYSES == 1


def test_bundled_web_ui_is_served(client):
    if not (Path(config.get_settings().WEBUI_DIR) / "index.html").exists():
        pytest.skip("web UI not built")
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert client.get("/login/").status_code == 200
    assert client.get("/analysis/").status_code == 200
    assert client.get("/api/health").json() == {"status": "ok"}  # API still takes precedence


def test_sqlite_uses_wal():
    if engine.dialect.name != "sqlite":
        pytest.skip("sqlite only")
    with engine.connect() as c:
        assert c.exec_driver_sql("PRAGMA journal_mode").scalar().lower() == "wal"


def _load_launcher():
    spec = importlib.util.spec_from_file_location("run_local", ROOT / "run_local.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_launcher_creates_env_with_valid_keys(tmp_path, monkeypatch):
    rl = _load_launcher()
    env = tmp_path / ".env"
    monkeypatch.setattr(rl, "ENV_FILE", env)
    rl.ensure_env()
    values = dict(line.split("=", 1) for line in env.read_text().splitlines() if "=" in line and not line.startswith("#"))
    Fernet(values["FILE_ENCRYPTION_KEY"].encode())  # valid Fernet key
    assert len(values["SECRET_KEY"]) >= 40 and values["TASK_MODE"] == "thread" and values["MAX_CONCURRENT_ANALYSES"] == "1"
    before = env.read_text()
    rl.ensure_env()  # never overwrites existing keys
    assert env.read_text() == before
    Fernet(rl.new_fernet_key().encode())


def test_start_bat_present():
    bat = (ROOT / "start.bat").read_text()
    assert "run_local.py" in bat and "python.org" in bat
