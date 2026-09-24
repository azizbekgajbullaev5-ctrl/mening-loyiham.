"""Test configuration: isolated SQLite DB + temp storage + synchronous jobs."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="aasa-test-"))
os.environ.update(
    {
        "ENV": "test",
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}"),
        "STORAGE_DIR": str(_TMP / "uploads"),
        "TASK_MODE": "inline",
        "SECRET_KEY": "test-secret-key-0123456789",
        "LOGIN_RATE_LIMIT_PER_MINUTE": "1000",
        "AUTO_RETRY_ATTEMPTS": "0",
        # make sure no real external provider is picked up from the environment
        "AI_DETECTOR_API_URL": "", "AI_DETECTOR_API_KEY": "", "SIMILARITY_API_URL": "", "SIMILARITY_API_KEY": "",
        "ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "LLM_REVIEW_ENABLED": "false",
    }
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import Base, engine  # noqa: E402
from app.core.security import login_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.providers import registry  # noqa: E402
from scripts.make_samples import make_docx, make_pdf, make_scanned_pdf, make_txt  # noqa: E402

SAMPLES = Path(__file__).parent / "fixtures" / "samples"


@pytest.fixture(scope="session", autouse=True)
def _db():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _reset():
    registry.set_overrides(None, None)
    login_limiter.reset()
    yield
    registry.set_overrides(None, None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


_counter = {"n": 0}


def register(client: TestClient, email: str | None = None, password: str = "correct-horse-42") -> dict:
    _counter["n"] += 1
    email = email or f"user{_counter['n']}_{os.getpid()}@example.org"
    r = client.post("/api/auth/register", json={"email": email, "password": password, "full_name": "Test User"})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def user_client():
    with TestClient(app) as c:
        register(c)
        yield c


@pytest.fixture(scope="session")
def samples() -> dict:
    out = {}
    for lang in ("uz", "ru", "en"):
        out[f"{lang}.docx"] = make_docx(lang)
        out[f"{lang}.pdf"] = make_pdf(lang)
        out[f"{lang}.txt"] = make_txt(lang)
    out["en_scanned.pdf"] = make_scanned_pdf("en")
    return out


def upload(client: TestClient, name: str, data: bytes, depth: str = "standard", doc_type: str = "phd_dissertation", **extra) -> dict:
    r = client.post(
        "/api/documents",
        files=[("files", (name, data, "application/octet-stream"))],
        data={"depth": depth, "doc_type": doc_type, **{k: str(v).lower() for k, v in extra.items()}},
    )
    assert r.status_code == 201, r.text
    return r.json()["items"][0]
