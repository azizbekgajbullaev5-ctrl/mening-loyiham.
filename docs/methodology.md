# Methodology

This document describes exactly what the analyzer measures, and what it does **not** measure.

> AI-detection results are probabilistic indicators and should not be interpreted as definitive proof of AI
> authorship. Similarity analysis and AI-likelihood analysis are separate measurements.

## 1. Pipeline

```
UPLOAD → FILE VALIDATION → TEXT EXTRACTION → LANGUAGE DETECTION → STRUCTURE DETECTION → SEGMENTATION
       → AI-LIKELIHOOD → SIMILARITY → STYLE → PARAPHRASE INDICATORS → ACADEMIC WRITING → AGGREGATION → REPORT
```

| Stage | Module |
|---|---|
| Validation (extension, magic bytes, size, zip-bomb, macros, optional ClamAV) | `backend/app/document_processing/validation.py` |
| Extraction (DOCX paragraphs/headings/tables/page breaks, PDF blocks + font-size headings + header/footer removal, OCR for scanned pages, TXT with encoding detection) | `backend/app/document_processing/extractors.py` |
| Language detection (script + stopwords + Uzbek orthography, per paragraph) | `backend/app/analyzers/languages/registry.py` |
| Structure (chapters, numbered sections, standard parts in uz/ru/en, TOC skipping, manual override) | `backend/app/document_processing/structure.py` |
| Segmentation (120–380-word passages with page/paragraph provenance) | `backend/app/document_processing/segmentation.py` |
| AI-likelihood | `backend/app/analyzers/ai_likelihood.py` |
| Similarity & paraphrase indicators | `backend/app/analyzers/similarity.py` |
| Style consistency | `backend/app/analyzers/style.py` |
| Academic writing | `backend/app/analyzers/academic.py` |
| Orchestration, progress, aggregation | `backend/app/services/pipeline.py` |

## 2. AI-likelihood (local, stylometric)

Each passage is described by up to 12 signals. Every signal is mapped to a 0–1 sub-score with a logistic
function whose midpoint/scale come from the **language profile** (`backend/app/analyzers/languages/{uz,ru,en}.py`),
so Uzbek text is not judged by English norms. The passage score is the weighted mean × 100.

| Signal | AI-like direction | Weight |
|---|---|---|
| Sentence-length coefficient of variation (burstiness) | low | 1.4 |
| Formulaic/generic academic phrase density (per-language list) | high | 1.6 |
| Share of sentences opening with a discourse marker | high | 1.1 |
| Repeated sentence openings | high | 0.6 |
| Repeated function-word templates (syntactic regularity) | high | 0.8 |
| Concrete specificity (numbers, citations, parentheses, quotes, names) | low | 1.3 |
| Lexical uniformity (std. of windowed type-token ratio) | low | 0.5 |
| "A, B and C" enumerations | high | 0.5 |
| Nominalisation / formalisation density | high | 0.4 |
| Vague intensifiers (crucial, innovative, samarali, ключевой, …) | high | 0.7 |
| Paragraph-length uniformity within the section | low | 0.5 |
| Sudden style shift vs. the document's own norm (only towards the AI-like side) | high | 0.6 |

Rules that keep this honest:

* At least three signals must be computable, otherwise the passage is **not scored** (no guessing).
  Passages under 40 words are not scored.
* **Confidence** depends on passage length, how far the score is from 50, and how many signals agree.
  It is capped per language: Uzbek never exceeds **Medium** (no validated corpus exists). OCR text and QUICK
  analyses also never reach High.
* References, table of contents, keywords, title page and appendices are excluded.
* Section/chapter/document scores are **word-weighted means** of passage scores, not counts of flags.
* The system only explains characteristics; it never rewrites text.

### Calibration status

The midpoints were set heuristically and sanity-checked on synthetic samples in
`backend/tests/fixtures/sample_texts.py`. **They have not been validated on a labelled corpus.** Before
high-stakes use, collect a labelled set of genuine human and AI-generated academic texts per language and
re-fit the baselines (see "Recommended next steps" in the README).

## 3. Similarity (separate module)

* **Internal repetition** — 6-word shingles (≥2 content words) shared by non-adjacent passages.
* **Own-corpus overlap** — winnowed shingle hashes of the *same user's* earlier documents (only hashes are
  stored; other users' documents are never compared).
* **Repeated phrases** — maximal 5–9-word phrases occurring ≥3 times.
* **Paraphrase indicators** — pairs of passages with high TF-IDF character-n-gram cosine (≥0.55) but low
  verbatim overlap (<0.2).
* **External similarity** — only when a similarity API is configured and DEEP analysis is chosen.

Without an external provider the report states: *"Local/document similarity analysis only."* No internet-wide
check is claimed.

## 4. Academic-writing indicators

Sentence length / long-sentence share, adjacent-sentence cohesion, academic vocabulary share, MATTR,
expected components per document family, citation style (numeric / author–year / mixed), citations
without a reference entry, uncited references, references without year, duplicate references, mixed
GOST/APA formats, heading numbering gaps, mixed heading capitalisation, mixed Uzbek apostrophes
(o' / oʻ / o\`), spelling variants, undefined abbreviations, repeated sentences, overused transitions.

These are formal/linguistic checks. **They do not assess scientific validity.**

## 5. External providers

See `docs/providers.md`. External results are shown next to the local estimate and are never averaged into
it. When methods disagree by ≥15 points the UI says: *"Results vary between analysis methods. The system
should not treat any individual score as definitive."*
