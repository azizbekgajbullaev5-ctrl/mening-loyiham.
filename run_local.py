"""Local launcher (no Docker): SQLite + in-process worker + bundled web UI.

Started by start.bat (Windows) or `python run_local.py` (any OS). All setup is
done here in plain Python — start.bat only runs this file. On every start it:
  0. creates backend/.venv on first run and re-runs itself with that Python,
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
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import venv
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
REQS = BACKEND / "requirements-core.txt"
ENV_FILE = BACKEND / ".env"
VENV = BACKEND / ".venv"
VENV_PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MARKER = Path(sys.prefix) / ".aasa-requirements.sha256"
# Versions with prebuilt wheels for every dependency; newer Pythons are used only as a fallback.
PREFERRED = ((3, 12), (3, 13), (3, 11))


def say(msg: str) -> None:
    print(msg, flush=True)


def in_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def _version_ok(v: tuple[int, int]) -> bool:
    return v >= (3, 11)


def base_python() -> list[str]:
    """Python used to create the venv: this one if it is a preferred version, else a preferred one via the py launcher."""
    if sys.version_info[:2] in PREFERRED:
        return [sys.executable]
    launcher = shutil.which("py")
    if launcher:
        for major, minor in PREFERRED:
            if subprocess.call([launcher, f"-{major}.{minor}", "-c", "pass"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                return [launcher, f"-{major}.{minor}"]
    if _version_ok(sys.version_info[:2]):
        return [sys.executable]
    say("\n[XATO] Python 3.11 yoki undan yangi versiya topilmadi.")
    say("Python 3.12 ni https://www.python.org/downloads/ saytidan yuklab o'rnating.")
    say("O'rnatishda \"Add python.exe to PATH\" belgisini albatta qo'ying.")
    sys.exit(1)


def ensure_venv_and_rerun() -> None:
    """Create backend/.venv once, then run this script again with the venv's Python."""
    if in_venv():
        return
    if not VENV_PYTHON.exists():
        base = base_python()
        say("Virtual muhit yaratilmoqda (backend\\.venv)...")
        if base == [sys.executable]:
            venv.EnvBuilder(with_pip=True).create(VENV)
        elif subprocess.call([*base, "-m", "venv", str(VENV)]) != 0:
            say("[XATO] Virtual muhit yaratilmadi.")
            sys.exit(1)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    sys.exit(subprocess.call([str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]], env=env))


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
                "# One query per 400 words (30 000 words -> 75 queries), at most WEB_MAX_QUERIES",
                "WEB_MAX_QUERIES=150",
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


# Defaults written into backend/.env by earlier versions that are now known to be too low.
# Only an unchanged old default is updated; a value the user edited is left alone.
ENV_UPGRADES = {"WEB_MAX_QUERIES=40": "WEB_MAX_QUERIES=150"}


def upgrade_env() -> None:
    if not ENV_FILE.exists():
        return
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    changed = [ln for ln in lines if ln.strip() in ENV_UPGRADES]
    if not changed:
        return
    ENV_FILE.write_text("\n".join(ENV_UPGRADES.get(ln.strip(), ln) for ln in lines) + "\n", encoding="utf-8")
    for ln in changed:
        say(f"  backend\\.env yangilandi: {ln.strip()} -> {ENV_UPGRADES[ln.strip()]}")


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
    ensure_venv_and_rerun()
    ensure_packages()
    if "--genkey" in sys.argv:
        print(new_fernet_key())
        return
    os.chdir(BACKEND)  # settings read backend/.env; relative data paths live in backend/data
    sys.path.insert(0, str(BACKEND))
    ensure_env()
    upgrade_env()
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
