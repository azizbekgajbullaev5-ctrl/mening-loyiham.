export type Confidence = "low" | "medium" | "high";

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_admin?: boolean;
}

export interface AnalysisSummary {
  id: string;
  queue_position: number | null;
  attempts: number;
  document_id: string;
  document_name: string | null;
  doc_type: string | null;
  depth: "quick" | "standard" | "deep";
  status: "queued" | "running" | "completed" | "failed" | "awaiting_confirmation";
  progress: number;
  stage: string;
  message: string;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  language: string | null;
  word_count: number | null;
  page_count: number | null;
  ai_likelihood: number | null;
  ai_confidence: Confidence | null;
  similarity_overall: number | null;
  corpus_check?: boolean;
  web_check?: boolean;
  web_estimate?: WebEstimate | null;
  originality?: number | null;
  borrowing?: number | null;
  citation?: number | null;
}

export interface WebEstimate {
  words: number;
  queries: number;
  max_pages: number;
  price_per_1000_usd: number;
  cost_usd: number;
  configured: boolean;
}

export interface PlagiarismSource {
  index: number;
  module: "corpus" | "own" | "web";
  module_label: string;
  title: string;
  url: string | null;
  authors: string;
  year: number | null;
  doc_kind: string | null;
  share_text: number;
  share_report: number;
  words: number;
  paraphrase_words: number;
  max_similarity: number | null;
}

export interface IntegrityItem {
  code: string;
  label: string;
  severity: "high" | "medium" | "low";
  count: number;
  examples?: string[];
  pages?: number[];
}

export interface Plagiarism {
  checked_words: number;
  excluded_words: number;
  originality: number;
  borrowing: number;
  citation: number;
  paraphrase_share: number;
  sources: PlagiarismSource[];
  spans: [number, number, number, number, "b" | "p" | "c"][];
  integrity: { suspicious: boolean; items: IntegrityItem[] };
  modules: {
    corpus?: boolean;
    own?: boolean;
    web?: boolean;
    paraphrase?: { backend: string; chunks: number; matches: number; threshold?: number } | false;
    corpus_documents?: number;
    web_stats?: WebStats;
    duplicates?: DuplicateDoc[];
  };
  exclusions: Record<string, number>;
}

export interface WebPage {
  url: string;
  title: string;
  status: string;
  cached: boolean;
  words: number;
  source_index?: number | null;
}

export interface WebStats {
  queries_planned?: number;
  queries_used: number;
  results_total?: number;
  queries_without_results?: number;
  fetched_pages: number;
  cached_pages: number;
  failed_pages: number;
  cost_usd: number;
  errors: string[];
  pages?: WebPage[];
  query_log?: { q: string; results: number | null; error?: string }[];
}

export interface DuplicateDoc {
  id: string;
  filename: string;
  uploaded_at: string | null;
  reasons: ("same_file" | "same_name" | "same_text")[];
  overlap: number | null;
  excluded: boolean;
}

export interface CorpusStats {
  documents: number;
  fingerprints: number;
  vectors: number;
  words: number;
  by_kind: Record<string, number>;
  by_source: Record<string, number>;
  by_language: Record<string, number>;
  database_bytes: number | null;
  embedding_backend: string;
}

export interface RefDocument {
  id: string;
  title: string;
  authors: string;
  year: number | null;
  doc_kind: string;
  source_type: string;
  source_url: string | null;
  doi: string | null;
  language: string;
  folder: string;
  filename: string;
  word_count: number;
  fingerprint_count: number;
  vector_count: number;
  fulltext: boolean;
  created_at: string;
}

export interface CorpusJob {
  id: string;
  kind: "ingest" | "harvest";
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  total: number;
  done: number;
  added: number;
  skipped: number;
  failed: number;
  message: string;
  log: string[];
  created_at: string;
  params: Record<string, unknown>;
}

export interface Version {
  page_count: number;
  pages_estimated: boolean;
  word_count: number;
  char_count: number;
  paragraph_count: number;
  language: string;
  language_confidence: number;
  language_distribution: Record<string, number>;
  is_scanned: boolean;
  ocr_used: boolean;
  structure_source: "auto" | "manual";
  warnings: string[];
}

export interface ProviderRow {
  name: string;
  kind: string;
  status: string;
  status_label: string;
  category?: string;
  errors?: string[];
}

export interface AcademicIssue {
  code: string;
  severity: "info" | "warning";
  severity_label: string;
  text: string;
}

export interface AnalysisResult {
  ai: {
    likelihood: number | null;
    confidence: Confidence;
    confidence_label: string;
    basis_text: string;
    note: string;
    passages_analyzed: number;
    passages_flagged: number;
    flagged_word_share: number;
    threshold: number;
    language_note: string | null;
  };
  similarity: {
    overall: number | null;
    internal: number | null;
    corpus: number | null;
    external: number | null;
    scope: string;
    scope_text: string;
    paraphrase_candidates: number;
  };
  providers: ProviderRow[];
  provider_comparison: {
    summary: string;
    summary_text: string;
    spread?: number;
    providers: { name: string; kind: string; passages_sent: number; passages_scored: number; mean_score: number | null; local_mean_same_passages: number | null; errors: string[] }[];
  };
  score_distribution: { range: string; count: number }[];
  passage_positions: { pos: number; score: number; flagged: boolean; page: number | null; chapter_order: number | null }[];
  style: { consistency: number | null; outliers: { order: number; title: string; deviation: number }[]; shifts: { from_title: string; to_title: string; magnitude: number }[] };
  academic: {
    metrics: Record<string, number>;
    components: { kind: string; label: string; present: boolean; word_count: number }[];
    citations: { style: string; in_text_count: number; missing_references: number[]; uncited_references: number[] };
    references: { count: number; with_year: number; year_min: number | null; year_max: number | null; duplicates: number };
    issues: AcademicIssue[];
  };
  repeated_phrases: { phrase: string; count: number }[];
  metrics: Record<string, unknown>;
  disclaimer: string;
}

export interface AnalysisDetail extends AnalysisSummary {
  version: Version | null;
  file_available: boolean;
  result: AnalysisResult | null;
}

export interface SectionRow {
  order: number;
  parent_order: number | null;
  kind: string;
  kind_label: string;
  level: number;
  title: string;
  page_start: number | null;
  page_end: number | null;
  word_count: number;
  ai_likelihood: number | null;
  ai_confidence: Confidence | null;
  ai_confidence_label: string | null;
  similarity: number | null;
  suspicious_count: number;
  excluded_from_ai: boolean;
}

export interface Passage {
  id: string;
  page: number | null;
  paragraph_number: number;
  paragraph_end_number: number;
  section_title: string | null;
  chapter_order: number | null;
  chapter_title: string | null;
  text: string;
  word_count: number;
  ai_likelihood: number;
  confidence: Confidence;
  confidence_label: string;
  characteristics: { code: string; label: string; detail: string }[];
  explanation: string;
  provider_scores: { provider: string; score: number; confidence: string | null; explanation: string | null }[];
}

export interface SimilarityMatch {
  id: string;
  match_type: string;
  match_type_label: string;
  section_title: string | null;
  page: number | null;
  paragraph_number: number | null;
  text: string;
  matched_text: string;
  matched_page: number | null;
  matched_paragraph_number: number | null;
  matched_document_name: string | null;
  source_title: string | null;
  source_url: string | null;
  similarity: number;
}

export interface ContentParagraph {
  index: number;
  number: number;
  text: string;
  kind: string;
  page: number | null;
  heading: { kind: string; level: number } | null;
}
