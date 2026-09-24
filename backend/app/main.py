from __future__ import annotations

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import analyses, auth, corpus, documents, system
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    if s.ENV != "production" and s.DATABASE_URL.startswith("sqlite"):
        # Development convenience; production uses Alembic migrations.
        import app.models  # noqa: F401
        from app.core.database import Base, engine

        Base.metadata.create_all(engine)
    if s.TASK_MODE == "thread":
        from app.tasks.maintenance import recover_interrupted
        from app.tasks.queue import enqueue_analysis

        for aid in recover_interrupted():
            enqueue_analysis(aid)
    if s.TASK_MODE == "thread":
        from app.plagiarism import jobs as corpus_jobs

        corpus_jobs.recover()
    from app.tasks.maintenance import start_periodic_cleanup

    start_periodic_cleanup()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=s.APP_NAME,
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if s.ENV == "production" else "/api/docs",
        openapi_url=None if s.ENV == "production" else "/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/_next/static/"):
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        else:
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    for r in (auth.router, documents.router, analyses.router, corpus.router, system.router):
        app.include_router(r, prefix=s.API_PREFIX)

    # Bundled web UI (static export of the Next.js frontend). Lets the app run from a
    # single Python process — used by the Windows launcher (start.bat). API routes above
    # take precedence; everything else is served from the export.
    webui = Path(s.WEBUI_DIR)
    if (webui / "index.html").exists():
        app.mount("/", StaticFiles(directory=webui, html=True), name="webui")
    return app


app = create_app()
