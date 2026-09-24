"""Local launcher (no Docker): SQLite + in-process worker + bundled web UI.

Started by start.bat (Windows) or `python run_local.py` (any OS) using the
Python inside backend/.venv. On every start it:
  1. installs/updates Python packages when requirements changed,
  2. creates backend/.env with fresh secret keys on first run,
  3. creates/upgrades the SQLite database,
  4. starts the server on a free local port and opens the browser.

    python run_local.py            # start
    python run_local.py --genkey   # print a new FILE_ENCRYPTION_KEY and exit
"""
from __future__ import annotations

import hashlib
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
REQS = BACKEND / "requirements-core.txt"
ENV_FILE = BACKEND / ".env"
MARKER = Path(sys.prefix) / ".aasa-requirements.sha256"


def say(msg: str) -> None:
    print(msg, flush=True)


def ensure_packages() -> None:
    digest = hashlib.sha256(REQS.read_bytes()).hexdigest()
    if MARKER.exists() and MARKER.read_text().strip() == digest:
        return
    say("\n[1/3] Kerakli Python kutubxonalari o'rnatilmoqda (birinchi marta 3-10 daqiqa, internet kerak)...")
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQS)]
    if subprocess.call([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check", "--upgrade", "pip"]) != 0:
        say("  (pip yangilanmadi — davom etamiz)")
    if subprocess.call(cmd) != 0:
        say("\n[XATO] Kutubxonalar o'rnatilmadi. Internet aloqasini tekshirib, start.bat ni qayta ishga tushiring.")
        sys.exit(1)
    MARKER.write_text(digest)


def new_fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def ensure_env() -> None:
    if ENV_FILE.exists():
        return
    say("[2/3] Birinchi ishga tushirish: maxfiy kalitlar yaratilmoqda (backend\\.env)...")
    ENV_FILE.write_text(
        "\n".join(
            [
                "# Created automatically by run_local.py. Keep this file private and back it up:",
                "# without FILE_ENCRYPTION_KEY the stored (encrypted) documents cannot be opened.",
                "ENV=production",
                f"SECRET_KEY={secrets.token_urlsafe(48)}",
                f"FILE_ENCRYPTION_KEY={new_fernet_key()}",
                "DATABASE_URL=sqlite:///./data/app.db",
                "STORAGE_DIR=./data/uploads",
                "TASK_MODE=thread",
                "MAX_CONCURRENT_ANALYSES=1",
                "AUTO_RETRY_ATTEMPTS=2",
                "MAX_UPLOAD_MB=60",
                "CORS_ORIGINS=http://127.0.0.1",
                "",
                "# Optional: path to tesseract.exe for scanned PDFs (auto-detected if installed normally)",
                "TESSERACT_CMD=",
                "",
                "# --- Plagiarism ---",
                "# Paraphrase embeddings: auto = model2vec (downloaded once, ~0.5 GB) or offline hash vectors",
                "EMBEDDING_BACKEND=auto",
                "# Internet check via Brave Search API (https://brave.com/search/api/). Cost is shown before each check.",
                "BRAVE_API_KEY=",
                "BRAVE_PRICE_PER_1000_USD=5.0",
                "WEB_MAX_QUERIES=40",
                "# Harvesting open sources into the reference corpus (comma-separated lists)",
                "HARVEST_OJS_URLS=",
                "HARVEST_QUERIES=",
                "OPENALEX_EMAIL=",
                "CROSSREF_MAILTO=",
                "CORE_API_KEY=",
                "",
                "# Optional external AI review for DEEP analysis (lightest Claude model by default):",
                "LLM_REVIEW_ENABLED=false",
                "ANTHROPIC_API_KEY=",
                "ANTHROPIC_MODEL=claude-haiku-4-5",
                "",
            ]
        ),
        encoding="utf-8",
    )


def migrate_database() -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from app.core.database import engine

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    tables = set(inspect(engine).get_table_names())
    if "users" in tables and "alembic_version" not in tables:
        command.stamp(cfg, "head")  # database created earlier without migrations
    command.upgrade(cfg, "head")


def free_port(start: int = 8000) -> int:
    for port in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise SystemExit("Bo'sh port topilmadi (8000-8049)")


def open_browser_when_ready(url: str) -> None:
    for _ in range(120):
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=1) as r:
                if r.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.5)


def main() -> None:
    if "--genkey" in sys.argv:
        print(new_fernet_key())
        return
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 yoki yangiroq versiya kerak")
    ensure_packages()
    os.chdir(BACKEND)  # settings read backend/.env; relative data paths live in backend/data
    sys.path.insert(0, str(BACKEND))
    ensure_env()
    say("[3/3] Ma'lumotlar bazasi tayyorlanmoqda...")
    migrate_database()

    import uvicorn

    from app.core.config import get_settings
    from app.document_processing.extractors import _ocr_available

    s = get_settings()
    if not (Path(s.WEBUI_DIR) / "index.html").exists():
        say("[OGOHLANTIRISH] backend/webui topilmadi — veb-interfeys yo'q (faqat API ishlaydi).")
    ocr = "bor" if _ocr_available() else "yo'q (skanerlangan PDF uchun Tesseract o'rnating)"
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    say("")
    say("=" * 64)
    say("  Akademik AI va o'xshashlik tahlilchisi ishga tushdi")
    say(f"  Brauzerda oching:  {url}")
    say(f"  OCR: {ocr}")
    say("  To'xtatish uchun shu oynani yoping (yoki Ctrl+C).")
    say("  Tahlil davom etayotganda oynani yopsangiz, keyingi ishga")
    say("  tushirishda tahlil saqlangan joyidan davom etadi.")
    say("=" * 64)
    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
