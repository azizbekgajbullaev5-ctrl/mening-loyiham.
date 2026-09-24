# Architecture

```
Browser ──► Next.js (frontend, :3000) ──/api/* proxy──► FastAPI (backend, :8000) ──► PostgreSQL
                                                             │  enqueue
                                                             ▼
                                                        Redis (RQ) ──► RQ workers (pipeline)
                                                                            │
                                                     encrypted file storage (Fernet) ◄┘
```

* The browser only talks to the Next.js origin; `/api/*` is rewritten server-side to the backend. Sessions
  use an httpOnly, SameSite=Lax cookie (Bearer tokens are also accepted for API clients).
* Uploads are validated, encrypted at rest and stored under random names outside any web root.
* **Local mode** (`run_local.py` / `start.bat`): one Python process serves the API *and* the statically exported
  UI from `backend/webui`, uses SQLite (WAL) and an in-process worker with one analysis at a time.
* Text extraction and OCR pages are checkpointed (`app/services/checkpoints.py`, Fernet-encrypted, keyed by
  document id + file hash) so failed or interrupted analyses resume instead of starting over.
* Analysis runs in background jobs (`TASK_MODE=rq` in production, in-process threads in development,
  synchronous in tests) and writes progress (`progress`, `stage`, `message`) to the `analyses` row, which the
  UI polls.

## Repository layout

```
backend/
  app/
    api/                   REST endpoints (auth, documents, analyses, reports, system)
    core/                  config, database, security, i18n (uz/en server texts)
    models/                SQLAlchemy entities
    document_processing/   validation, extractors (DOCX/PDF/TXT/OCR), structure, segmentation
    analyzers/             ai_likelihood, similarity, style, academic, languages/{uz,ru,en}.py
    providers/             provider interfaces, local + external/LLM adapters, retry/cache
    services/              pipeline orchestration, encrypted storage, audit log
    reporting/             PDF (ReportLab) and DOCX (python-docx) reports
    tasks/                 queue dispatch, retention cleanup
  alembic/                 migrations
  tests/                   pytest suite; fixtures/documents.py generates synthetic uz/ru/en samples,
                           fixtures/hostile.py builds rejected-upload inputs in a temp folder
frontend/                  Next.js 14 + TypeScript + Tailwind + Recharts (Uzbek UI)
docker/                    Dockerfiles
docs/                      this documentation
portal/                    the earlier static "OAK journals" site (GitHub Pages)
```

## Data model

| Table | Content |
|---|---|
| `users` | email, argon2 password hash |
| `documents` | owner, file name/type/size/sha256, encrypted storage key, doc type |
| `document_versions` | extraction metadata (pages, words, language, OCR), heading structure (auto/manual) |
| `analyses` | depth, status, progress, stage, errors, timings |
| `analysis_results` | document-level AI estimate + confidence, similarity figures and scope, providers used, comparisons, chart data, style, academic, repeated phrases |
| `section_results` | per chapter/section AI estimate, confidence, similarity, flagged count |
| `passage_analyses` | **only flagged passages**, with text, page, paragraph, characteristics |
| `similarity_matches` | internal / cross-document / paraphrase / external matches |
| `document_fingerprints` | winnowed shingle hashes (no text) for same-owner comparison |
| `reports` | report generation log |
| `provider_cache` | cached external results keyed by passage hash |
| `audit_logs` | security-relevant events (no document content) |

Full document text is never stored in the database; the document viewer re-extracts it on demand from the
encrypted file.

## Adding a language

1. Create `backend/app/analyzers/languages/<code>.py` with a `LanguageProfile` (stopwords, transitions,
   generic phrases, qualifiers, heading keywords, abbreviations, baselines, `max_confidence`).
2. Register it in `PROFILES` in `registry.py`.
3. Add sample texts and tests; calibrate baselines on real labelled data.

## Adding an interface language

Frontend strings live in `frontend/lib/i18n.ts` (add a dictionary with the same keys); server-side report
and explanation texts live in `backend/app/core/i18n.py` and `backend/app/reporting/builder.py` (uz and en
exist).
