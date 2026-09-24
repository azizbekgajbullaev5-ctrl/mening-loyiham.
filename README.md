# Academic AI & Similarity Analyzer

**Akademik AI va o'xshashlik tahlilchisi** — PhD va magistrlik dissertatsiyalari, darsliklar, o'quv
qo'llanmalar, ilmiy maqolalar, konferensiya materiallari va ilmiy hisobotlarni **akademik sifat nazorati**
uchun tahlil qiluvchi veb-ilova (interfeys tili: o'zbekcha).

It analyzes academic documents (DOCX / PDF / TXT, Uzbek-Latin / Russian / English) for:

* **AI-likelihood** — a probabilistic estimate of AI-like writing characteristics, per passage, section and
  chapter, with a LOW / MEDIUM / HIGH confidence label and an explanation;
* **similarity** — a *separate* measurement: internal repetition, overlap with the user's own earlier
  documents, repeated phrases, paraphrase indicators, and (optionally) an external similarity service;
* **style consistency** and **academic-writing indicators** — citations vs. references, heading numbering,
  terminology and apostrophe consistency, missing dissertation components, overused transitions, etc.

> **AI-detection results are probabilistic indicators and should not be interpreted as definitive proof of AI
> authorship. Similarity analysis and AI-likelihood analysis are separate measurements.**
> This tool is not a "100% accurate AI detector", does not "guarantee" detection of any model, and has no
> feature for rewriting text to evade detectors. Its purpose is academic document analysis and quality control.

The earlier static "OAK journals" site now lives in [`portal/`](portal/) and is still published to GitHub
Pages (the workflow uploads `portal/` only).

---

## Contents

1. [Quick start (Docker)](#1-quick-start-docker)
2. [Local development](#2-local-development)
3. [Environment variables](#3-environment-variables)
4. [Database setup](#4-database-setup)
5. [Production deployment](#5-production-deployment)
6. [Optional external APIs](#6-optional-external-apis)
7. [Using the application](#7-using-the-application)
8. [Testing](#8-testing)
9. [What is local vs. external](#9-what-is-local-vs-external)
10. [Known limitations](#10-known-limitations)
11. [Recommended next steps](#11-recommended-next-steps)

Further reading: [`docs/methodology.md`](docs/methodology.md) · [`docs/architecture.md`](docs/architecture.md) ·
[`docs/providers.md`](docs/providers.md)

---

## 1. Quick start (Docker)

Requirements: Docker 24+ with Compose v2.

```bash
cp .env.example .env
# fill in at least:
#   SECRET_KEY          python -c "import secrets; print(secrets.token_urlsafe(48))"
#   FILE_ENCRYPTION_KEY python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#   POSTGRES_PASSWORD   any strong password
docker compose up -d --build
```

Open <http://localhost:3000>, register, and upload a document. The stack is PostgreSQL 16, Redis 7, the
FastAPI backend (runs `alembic upgrade head` on start), two RQ workers (with Tesseract OCR for uz/ru/en), and
the Next.js frontend. Only the frontend port is published; it proxies `/api/*` to the backend.

## 2. Local development

Requirements: Python 3.11+, Node 20+ (22 recommended). PostgreSQL/Redis are optional in development.
Tesseract (`tesseract-ocr` + `-rus` + `-uzb` language packs) is optional and only needed for scanned PDFs.

```bash
# backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
#  - uses SQLite (backend/data/dev.db) and in-process worker threads by default
#  - API docs: http://localhost:8000/api/docs

# frontend (second terminal)
cd frontend
npm install
npm run dev            # http://localhost:3000, proxies /api to http://localhost:8000
```

To develop against PostgreSQL + Redis like production:

```bash
export DATABASE_URL=postgresql+psycopg2://aasa:aasa@localhost:5432/aasa
export TASK_MODE=rq REDIS_URL=redis://localhost:6379/0
cd backend && alembic upgrade head
uvicorn app.main:app --port 8000        # terminal 1
rq worker -u $REDIS_URL analysis        # terminal 2
```

Sample documents (synthetic, uz/ru/en; DOCX, PDF, TXT and a scanned PDF) are in
`backend/tests/fixtures/samples/`; regenerate them with `python backend/scripts/make_samples.py`.

## 3. Environment variables

All configuration is read by the backend from the environment (or `.env`). See
[`.env.example`](.env.example) for the full, commented list. The most important ones:

| Variable | Default | Purpose |
|---|---|---|
| `ENV` | `development` | `production` disables API docs and **requires** `SECRET_KEY` and `FILE_ENCRYPTION_KEY` |
| `SECRET_KEY` | dev value | JWT signing key |
| `FILE_ENCRYPTION_KEY` | derived in dev | Fernet key used to encrypt stored uploads |
| `DATABASE_URL` | SQLite file | e.g. `postgresql+psycopg2://user:pass@host:5432/db` |
| `REDIS_URL` / `TASK_MODE` | `thread` | `rq` (production), `thread` (dev), `inline` (tests) |
| `COOKIE_SECURE` | `false` | set `true` behind HTTPS |
| `MAX_UPLOAD_MB`, `MAX_FILES_PER_UPLOAD` | 50, 10 | upload limits |
| `DELETE_FILES_AFTER_ANALYSIS`, `RETENTION_DAYS` | false, 0 | automatic clean-up of original files |
| `CLAMAV_HOST` | empty | optional clamd malware scanning of uploads |
| `OCR_ENABLED`, `OCR_LANGUAGES`, `OCR_MAX_PAGES` | true, `uzb+rus+eng`, 400 | OCR for scanned PDFs |
| `SUSPICIOUS_THRESHOLD` | 60 | passage AI-likelihood at which a passage is listed as suspicious |
| `EXTERNAL_MAX_PASSAGES` | 40 | cost cap: passages sent to each external provider per document |
| `AI_DETECTOR_*`, `SIMILARITY_*`, `ANTHROPIC_*`, `OPENAI_*`, `LLM_REVIEW_ENABLED` | empty/false | optional providers (section 6) |

The frontend needs only `BACKEND_URL` (server-side, used for the `/api` proxy). **No key is ever sent to the
browser.**

## 4. Database setup

```bash
createuser aasa -P && createdb aasa -O aasa          # or use the docker compose postgres service
cd backend
DATABASE_URL=postgresql+psycopg2://aasa:<pw>@localhost:5432/aasa alembic upgrade head
```

Create new migrations after model changes with
`alembic revision --autogenerate -m "describe change"`. In development with SQLite the tables are created
automatically on start.

## 5. Production deployment

* Use `docker compose up -d --build` (or the two Dockerfiles in `docker/` on your orchestrator).
* Put a TLS-terminating reverse proxy (nginx, Caddy, a cloud load balancer) in front of the frontend on
  port 3000 and set `COOKIE_SECURE=true` and `CORS_ORIGINS=https://your-domain`.
* Keep the backend unpublished (internal network only); the frontend proxies to it.
* Scale analysis throughput with `docker compose up -d --scale worker=N`. Each job has a 1-hour timeout and
  up to 2 automatic retries.
* Back up the `pgdata` and `uploads` volumes. Keep `FILE_ENCRYPTION_KEY` safe: without it stored files can't
  be decrypted. Rotating it makes existing stored originals unreadable (results remain).
* Consider `RETENTION_DAYS` or `DELETE_FILES_AFTER_ANALYSIS=true` for confidential research, and `CLAMAV_HOST`
  for malware scanning.
* Upload size is also limited by your reverse proxy (e.g. nginx `client_max_body_size 60m;`).

## 6. Optional external APIs

Nothing external is required. Without providers, results say *"Result based on local linguistic analysis."*
and *"Local/document similarity analysis only."*, and every external provider is listed as
*"External provider not configured."*

| Provider | Enable with | Used |
|---|---|---|
| Generic AI-detection API | `AI_DETECTOR_API_URL` + `AI_DETECTOR_API_KEY` (+ score field/scale) | DEEP analysis, top suspicious passages |
| Generic similarity/plagiarism API | `SIMILARITY_API_URL` + `SIMILARITY_API_KEY` | DEEP analysis, all body passages (batched) |
| LLM-assisted stylistic review (Claude) | `LLM_REVIEW_ENABLED=true` + `ANTHROPIC_API_KEY` (`ANTHROPIC_MODEL`, default `claude-opus-5`) | DEEP analysis, top suspicious passages |
| LLM-assisted stylistic review (OpenAI) | `LLM_REVIEW_ENABLED=true` + `OPENAI_API_KEY` | DEEP analysis, top suspicious passages |

Provider results are cached by passage hash, rate-limited, retried on 429/5xx and shown side by side with the
local estimate. They are never averaged into a single "truth". The request/response contracts and how to add
a vendor-specific adapter are described in [`docs/providers.md`](docs/providers.md).

## 7. Using the application

**Uploading a dissertation**

1. Register / log in.
2. On *Bosh sahifa*, drop one or more DOCX/PDF/TXT files onto *Hujjat yuklash*, choose the document type
   (e.g. *PhD dissertatsiya*) and analysis depth:
   * **Tezkor (Quick)** — sampled passages per section, local only;
   * **Standart (Standard)** — all passages, local AI + similarity (incl. your earlier documents);
   * **Chuqur (Deep)** — Standard + configured external providers for the most suspicious passages.
3. Click *Tahlilni boshlash*. Progress (extraction → language → structure → AI analysis per chapter →
   similarity → style → academic → aggregation) is shown live. In testing, a synthetic ~300-page DOCX was
   processed in about 20 seconds; scanned PDFs take longer because of OCR.

**Reading results** — tabs *Umumiy* (overview, both measurements, providers, charts), *Boblar* (chapter/section
table), *Shubhali parchalar* (flagged passages with page, paragraph, AI-likelihood, confidence,
characteristics and explanation; filter by chapter, minimum score, confidence, and search), *O'xshashlik*
(matches and repeated phrases), *Akademik yozuv*, *Hujjat* (document viewer with highlighted passages) and
*Metodologiya*.

**Correcting the structure** — *Tuzilmani tuzatish* lists the paragraphs; change which ones are headings and
their type/level, then save to re-run the analysis with the corrected structure.

**Generating a report** — *PDF hisobot* or *DOCX hisobot* on the result page. Reports contain document
information, language, word/page counts, AI-likelihood + confidence, similarity (with its scope), chapter
analysis, suspicious passages, similar passages, academic indicators, methodology, limitations and the
analysis date/time. `GET /api/analyses/{id}/report?format=pdf|docx&lang=uz|en` also works for API clients.

**Deleting** — *O'chirish* permanently deletes the document, its stored file, fingerprints, analyses and
reports. `DELETE /api/documents/{id}/file` deletes only the original file and keeps the results.

## 8. Testing

```bash
cd backend
pytest                                   # 91 tests, SQLite, ~1 minute
TEST_DATABASE_URL=postgresql+psycopg2://aasa:aasa@localhost:5432/aasa_test pytest   # same suite on PostgreSQL

cd frontend
npm run typecheck && npm run lint && npm run build
# browser end-to-end test against a running stack (see section 2):
npm run e2e          # set CHROMIUM_PATH if Playwright's bundled browser isn't installed
```

The backend suite covers DOCX/PDF/TXT parsing (incl. page numbers, tables, cp1251, header/footer removal),
OCR of a scanned PDF (skipped if Tesseract is absent), upload validation (bad signatures, macros, zip bombs,
size), language detection, section and TOC detection, chunking, scoring behaviour per language, confidence
caps, similarity (internal, same-owner corpus, owner isolation), academic checks, authentication and rate
limiting, authorization between users, deletion, encryption at rest, manual structure correction, PDF/DOCX
reports, external provider success/429 retry/failure/caching/comparison, and a ~300-page dissertation.

## 9. What is local vs. external

| Feature | Implementation |
|---|---|
| Text extraction, OCR, structure, segmentation | local |
| Language detection (uz / ru / en) | local |
| AI-likelihood estimate | **local stylometric analysis** (per-language profiles) |
| Similarity: internal, own documents, repeated phrases, paraphrase indicators | local |
| Similarity against internet / publication databases | **external only** (not performed unless configured) |
| Additional AI-detector scores / LLM review | **external only** (optional, DEEP analysis) |
| Academic-writing and style checks, reports | local |

## 10. Known limitations

* **The local AI-likelihood estimator is heuristic and has not been validated on a labelled corpus.** It is
  a stylometric indicator, not a trained classifier. Formal, formulaic human writing (common in Uzbek and
  Russian academic style) can score high; lightly edited AI text can score low.
* No validated Uzbek AI-text corpus exists; Uzbek confidence is therefore capped at *Medium*. Uzbek Cyrillic
  is detected but not supported by a dedicated module (results fall back to generic features with *Low*
  confidence).
* Without an external similarity API, there is **no internet or database plagiarism check**; cross-document
  comparison covers only the same user's own uploads.
* DOCX page numbers come from Word's saved page-break markers; when a file has none (e.g. generated
  documents), pages are estimated (~280 words/page) and labelled as estimated. TXT pages are estimated
  unless the file contains form feeds.
* PDF heading detection relies on font size/bold; unusual layouts may need manual structure correction.
  Multi-column PDFs and complex tables are extracted as plain text blocks.
* OCR quality depends on the scan; OCR text is never given *High* confidence.
* The "paraphrase" indicator finds meaning-level overlap *inside the document* only.
* Interface language is Uzbek; reports are available in Uzbek and English. Russian/English UI dictionaries
  are not yet written.
* The Docker images were written and the compose file validated, but they could not be built in the
  development sandbox used here (no Docker daemon); the same stack was verified by running its components
  directly (PostgreSQL 16, Redis 7, API with Alembic migrations, RQ worker, Next.js production build).

## 11. Recommended next steps

1. **Calibrate on real data.** Collect a labelled, consented corpus of human-written and AI-generated
   academic passages per language (especially Uzbek), fit the baselines/weights, and publish measured
   false-positive/false-negative rates. Until then, treat scores as screening indicators only.
2. Add a model-based perplexity signal (e.g. a small multilingual LM served locally) as another provider.
3. Connect a licensed similarity database (institutional repository, Crossref/CORE, national dissertation
   archive) through `SimilarityProvider`.
4. Russian and English interface dictionaries; Uzbek Cyrillic language profile.
5. Institution features: roles (supervisor / reviewer), shared workspaces, SSO.
6. Streaming progress (SSE) instead of polling; per-user quotas for DEEP analysis.
