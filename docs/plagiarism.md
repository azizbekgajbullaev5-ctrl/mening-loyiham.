# Plagiarism check (Antiplagiat-style)

This module checks a document against three kinds of sources and reports **originality / borrowing /
citation** percentages (they add up to 100% of the checked words), a list of sources with each source's
share, the text coloured by source and a PDF report laid out like the Antiplagiat.uz report.

It is separate from the AI-likelihood estimate: a borrowed passage is not "AI text", and an original
passage is not "human text".

## Sources

| Module | What is compared | Needs |
|---|---|---|
| Reference corpus (`Ma'lumotnoma bazasi`) | documents uploaded by an admin or collected by the harvester | nothing (local) |
| Own documents | the same user's earlier uploads (when "keep for similarity" is on) | nothing (local) |
| Internet | web pages found with the Brave Search API for the most distinctive sentences | `BRAVE_API_KEY` |
| Paraphrase | meaning-level matches with corpus chunks (multilingual embeddings) | nothing (model downloaded once, or hash fallback) |

### Reference corpus

* **Bulk upload by folder** — page *Ma'lumotnoma bazasi* (`/corpus/`), admin only. Choose a folder; every
  DOCX/PDF/TXT in it (and in its sub-folders) is sent in batches of 20. The folder path is stored.
* The corpus stores **only fingerprints and vectors**: winnowed 6-word shingle hashes with positions,
  50-word chunk embeddings (float16) and a document centroid. The text and the file are deleted after
  indexing. Duplicates are rejected by content hash and DOI.
* The page shows the number of documents, words, fingerprints, vectors and the database size, and lets an
  admin delete a document from the corpus.
* Admins: the first registered user, plus anyone listed in `ADMIN_EMAILS`.

### Harvester

Page *Ma'lumotnoma bazasi → Ochiq manbalardan yig'ish*. Jobs run one at a time in the background, survive a
restart (`recover()` on start) and can be cancelled. Every collected item goes through the same indexing.

| Source | How | Settings |
|---|---|---|
| Uzbek OJS journals | OAI-PMH `ListRecords` (oai_dc, resumption tokens); PDF galley links | `HARVEST_OJS_URLS` (comma-separated journal base URLs) |
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
