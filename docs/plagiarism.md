# Plagiarism check (Antiplagiat-style)

This module checks a document against three kinds of sources and reports **originality / borrowing /
citation** percentages (they add up to 100% of the checked words), a list of sources with each source's
share, the text coloured by source and a PDF report laid out like the Antiplagiat.uz report.

It is separate from the AI-likelihood estimate: a borrowed passage is not "AI text", and an original
passage is not "human text".

## Check modules

Every analysis has a list of enabled modules (`Analysis.check_modules`), chosen on upload, on the
confirmation page and — for a re-check — on the result page. The result page and the PDF say
**"N ta moduldan M tasida tekshirilgan"** and list each module as *checked / off / not configured / error*
(a module where not a single request succeeded is *error* and not counted).

| Module | Kind | What it compares with | Needs | Price |
|---|---|---|---|---|
| `corpus` Ma'lumotnoma bazasi | local | uploaded / harvested reference documents (verbatim + paraphrase) | — | free |
| `own` Sizning hujjatlaringiz | local | the user's other uploads (earlier copies excluded) | — | free |
| `ojs` O'zbek OJS jurnallari | local | articles harvested via OAI-PMH from `HARVEST_OJS_URLS` (own module) | journal URLs | free |
| `scholarly` Ilmiy bazalar | online | OpenAlex, Crossref, Semantic Scholar, CORE, arXiv: abstracts + open-licence full texts | CORE: free key | free (rate-limited) |
| `cyberleninka` CyberLeninka | online | open Russian articles (annotation + PDF) | — | free |
| `patents` Patentlar | online | Lens.org patent API: abstract, claims, description | `LENS_API_TOKEN` | free for scholarly use |
| `legal` Me'yoriy hujjatlar | online | lex.uz pages found via Brave `site:lex.uz` | `BRAVE_API_KEY` | Brave price |
| `web` Internet | online | pages found via Brave Search | `BRAVE_API_KEY` | Brave price |
| `translation` Tarjima | local | cross-language matches (uz ↔ ru ↔ en) with the multilingual model | model2vec | free |
| `templates` Shablon iboralar | filter | standard phrases are removed from borrowing | — | free |

Before an analysis with online modules starts it waits in `awaiting_confirmation`; the page shows per module
the number of queries, API calls, downloads, approximate time and price, and modules can be switched off.
Queries per online module: one per `MODULE_WORDS_PER_QUERY` (1000) words, at most `MODULE_MAX_QUERIES` (40);
`MODULE_RESULTS_PER_QUERY` results and up to `MODULE_FULLTEXT_PER_QUERY` open full texts per query.

**Licences and site rules.** Only open APIs are called, with their polite limits (arXiv ≤ 1 request / 3 s,
Semantic Scholar 1/s without a key, OpenAlex/Crossref with the configured contact e-mail). Full texts are
downloaded only when the record carries an open licence (Creative Commons / public domain) or comes from
an open-access API (CORE, arXiv); otherwise only the abstract returned by the API is compared. Every page,
PDF, OJS OAI endpoint/article page and the CyberLeninka search are fetched only if `robots.txt` allows it.
Google Patents is not used (no public API; its terms do not allow automated querying). lex.uz legal acts
are official documents. Nothing but fingerprints / vectors is cached.

**Translation.** Chunk vectors of the checked text are compared with corpus chunks and with online texts in
another language (`TRANSLATION_THRESHOLD`, default 0.80, heuristic). It needs the multilingual model
(`minishlab/potion-multilingual-128M`, static embeddings, ~0.5 GB, a few hundred MB RAM); with hash vectors
the module is shown as not configured. If the first start chose hash vectors (no internet), delete
`backend/data/models/embedding_backend.txt` while online and restart; documents indexed with hash vectors
must be re-added to the corpus to be compared semantically.

**Template phrases** (~100 uz/ru/en phrases such as "mavzuning dolzarbligi", "ushbu ishda", "актуальность
темы", "the aim of this study"; extend with `TEMPLATE_PHRASES`): their words are removed from matches, and
a match that becomes shorter than `PLAGIARISM_MIN_SOURCE_WORDS` disappears.

## Sources

| Module | What is compared | Needs |
|---|---|---|
| Reference corpus (`Ma'lumotnoma bazasi`) | documents uploaded by an admin or collected by the harvester | nothing (local) |
| Own documents | the same user's earlier uploads (when "keep for similarity" is on) | nothing (local) |
| Internet | web pages found with the Brave Search API for the most distinctive sentences | `BRAVE_API_KEY` |
| Paraphrase | meaning-level matches with corpus chunks (multilingual embeddings) | nothing (model downloaded once, or hash fallback) |

### Earlier copies of the same document

An earlier upload of the same work by the same user is not a source. A document is treated as a copy (left
out of the own-documents comparison and of the similarity tab, and reported as *"Bu hujjat avval
yuklangan"*) when it has the same file hash, or (nearly) the same text (≥ 90% of the larger document's
fingerprints shared), or the same file name (ignoring "(1)", "copy", "nusxa" suffixes) with ≥ 50% shared text.
A same-named file with different text is still compared and only mentioned in the warning.

### Reference corpus

* **Bulk upload by folder** — page *Ma'lumotnoma bazasi* (`/corpus/`), admin only. Choose a folder; every
  DOCX/PDF/TXT in it (and in its sub-folders) is sent in batches of 20. The folder path is stored.
* The corpus stores **only fingerprints and vectors**: winnowed 6-word shingle hashes with positions,
  50-word chunk embeddings (float16) and a document centroid. The text and the file are deleted after
  indexing. Duplicates are rejected by content hash and DOI.
* The page shows the number of documents, words, fingerprints, vectors and the database size, and lets an
  admin delete a document from the corpus.
* Admins: the first registered user, plus anyone listed in `ADMIN_EMAILS`.

### Bulk import (hundreds of files)

* Folder picker in the browser (batches of 20 files, up to 500 per request).
* **ZIP archive**: `POST /api/corpus/upload-zip` — up to `CORPUS_MAX_ZIP_MB` (1 GB), `CORPUS_MAX_FILES_PER_IMPORT`
  (5000) documents; entries with an extreme compression ratio (zip bombs), macros or wrong signatures are
  skipped; inner folders are kept.
* **Local folder path** (single-PC mode: SQLite + thread worker, or `CORPUS_LOCAL_IMPORT=true`):
  `POST /api/corpus/import-folder {"path": "C:\\Kutubxona"}` — files are read in place (never copied or
  deleted), validated like uploads.

### Harvester

Page *Ma'lumotnoma bazasi → Ochiq manbalardan yig'ish*. Jobs run one at a time in the background, survive a
restart (`recover()` on start) and can be cancelled. Every collected item goes through the same indexing.

| Source | How | Settings |
|---|---|---|
| Uzbek OJS journals | OAI-PMH `ListRecords` (oai_dc, resumption tokens); PDF galley links (looked up only for new articles) | `HARVEST_OJS_URLS` (comma-separated journal base URLs); `OJS_AUTO_HARVEST_HOURS` re-harvests automatically |
| OpenAlex | `/works?search=` with open-access filter; abstract or OA PDF | `HARVEST_QUERIES`, `OPENALEX_EMAIL`, `OPENALEX_FILTER` |
| CORE | `/v3/search/works` with full text | `CORE_API_KEY` (free) |
| Crossref | `/works?query=`; abstract (JATS stripped) or full-text link | `CROSSREF_MAILTO` |
| CyberLeninka | site search API; article PDF | — |

`HARVEST_MAX_PER_SOURCE`, `HARVEST_FETCH_FULLTEXT`, `HARVEST_MIN_TEXT_CHARS` and `HARVEST_RPS` limit
volume and speed. A failing source is logged in the job and does not stop the others.

### Internet check (Brave Search)

* Enabled per upload with *Internet tekshiruvi (Brave Search)*. Before anything is sent the analysis waits in
  status `awaiting_confirmation` and shows the **number of queries and the approximate price**:
  `queries = min(WEB_MAX_QUERIES, ceil(words / WEB_WORDS_PER_QUERY))`,
  `price = queries × BRAVE_PRICE_PER_1000_USD / 1000`. The user confirms or skips.
* Queries are the most distinctive sentences (rare words, spread across the document), skipping sentences
  already matched in the corpus and quoted/cited sentences. Only these short fragments leave the computer.
  Defaults: one query per 400 words (`WEB_WORDS_PER_QUERY`), at most `WEB_MAX_QUERIES=150`, 5 results per
  query, at most `WEB_MAX_PAGES=300` pages downloaded by `WEB_FETCH_WORKERS=6` parallel workers.
* Queries are **plain** (up to 18 words, unquoted). Earlier versions sent a quoted 12-word exact phrase, which
  almost never matched Uzbek pages (apostrophe variants oʻ/o‘/o', word forms), so Brave returned nothing.
  Whether a page really matches is decided by shingle comparison, not by the search engine.
* Every run records what happened: per query the number of results, per page the status (`ok`, `timeout`,
  `http_403`, `robots_disallow`, …) and whether it became a source. The result page and the PDF list the
  checked URLs. Failed pages are retried after 24 hours; successful ones are cached for `WEB_PAGE_CACHE_DAYS`.
* Found pages are downloaded with an SSRF guard (public IPs only, ports 80/443, re-checked on every
  redirect), `robots.txt` is respected (`WEB_RESPECT_ROBOTS`), size is limited (`WEB_MAX_PAGE_MB`). Only
  page fingerprints are cached (`WEB_PAGE_CACHE_DAYS`), not the page text.
* The key stays on the server; the browser only sees whether it is configured.

## Algorithm

1. **Normalisation** — NFC, invisible characters removed, apostrophe variants unified, homoglyphs mapped to
   the word's dominant script, Uzbek/Russian Cyrillic transliterated to Latin. So a Cyrillic copy of a
   Latin source (or a mixed-alphabet word) still matches.
2. **Exclusions** — reference list, table of contents, title page, tables and formula-like lines are not
   checked. Quoted passages followed by a reference (`[3]`, `(Karimov, 2020)`) are **citations**.
3. **Verbatim matching** — the document's shingles are looked up in the corpus / own documents / web pages;
   hits are joined into runs when the positions are consistent. Runs shorter than
   `PLAGIARISM_MIN_SOURCE_WORDS` are ignored.
4. **Paraphrase** — 50-word windows (stride 25) are embedded; the `PARAPHRASE_CANDIDATE_DOCS` corpus
   documents with the closest centroids are compared chunk by chunk. A paragraph is marked only if a window
   *and* the whole paragraph are close to the same source chunk.
   * `EMBEDDING_BACKEND=auto` uses `minishlab/potion-multilingual-128M` (model2vec: static embeddings, no
     PyTorch, ~0.5 GB download once into `MODEL_CACHE_DIR`, a few hundred MB of RAM); if it cannot be
     loaded it falls back to a character n-gram hashing vectorizer (weaker, but no download). The choice is
     remembered so the corpus and checks use the same vectors.
   * Thresholds: `PARAPHRASE_THRESHOLD_MODEL=0.88`, `PARAPHRASE_THRESHOLD_HASH=0.80`.
5. **Shares** — each word is assigned to citation, borrowing or original. Each source gets a *share in the
   text* (all words it matches; sources may overlap) and a *share in the report* (words attributed to it
   exclusively, largest source first, so they add up to the borrowing percentage).
6. **Technical tricks** — reported separately (they do not change the percentages): Latin/Cyrillic
   homoglyphs inside words, invisible characters (zero-width, soft hyphen, …), hidden text (DOCX `vanish`,
   white or ≤2 pt text; white/tiny PDF text), letters separated by spaces and unusual space characters.

## Results

* Result page, tab **Plagiat**: three tiles and a bar, modules used, sources table, tricks, and the text
  with passages coloured by source (`[n]` marks the source number; italic = paraphrase; green = citation).
* **Antiplagiat PDF**: `GET /api/analyses/{id}/report?kind=plagiarism` — title, document information,
  originality/borrowing/citation with a bar, definitions, scope, sources table, technical tricks, checked
  text with highlights, disclaimer.
* API: `GET /api/analyses/{id}/plagiarism`, `POST /api/analyses/{id}/confirm`, `/api/corpus/*`.

## Resource use (8 GB Windows PC)

* Analyses and corpus jobs each run one at a time.
* Corpus lookups use the database index; only centroids of the corpus are kept in memory
  (≈ 256 dims × 4 bytes per document).
* Embedding model: static model2vec (no neural network at run time) — fast on CPU.

## Limitations (honest)

* The result covers **only the sources checked**: the corpus you built, your own documents and (if used)
  the web pages Brave returned. A low borrowing percentage does not prove that a text is original.
* Paraphrase thresholds are heuristic and were tuned on a small synthetic set; review marked paragraphs.
* Brave, OpenAlex, CORE, Crossref, OJS, CyberLeninka and the model download were tested with mocked
  responses only (the development sandbox had no access to them); check them once on a real connection.
* Scanned PDFs need OCR; OCR errors reduce verbatim matches.
