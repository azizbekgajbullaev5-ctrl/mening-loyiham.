"""Application configuration, loaded from environment variables.

Secrets (API keys, SECRET_KEY, FILE_ENCRYPTION_KEY) are only ever read on the
server and are never returned by any API endpoint.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- general ---
    ENV: Literal["development", "test", "production"] = "development"
    APP_NAME: str = "Academic AI & Similarity Analyzer"
    API_PREFIX: str = "/api"
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- security ---
    SECRET_KEY: SecretStr = SecretStr("dev-insecure-secret-change-me")
    ACCESS_TOKEN_MINUTES: int = 60 * 12
    COOKIE_SECURE: bool = False
    FILE_ENCRYPTION_KEY: SecretStr = SecretStr("")  # Fernet key; required in production
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10

    # --- database / queue ---
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'dev.db'}"
    REDIS_URL: str = "redis://localhost:6379/0"
    TASK_MODE: Literal["rq", "thread", "inline"] = "thread"
    # In-process mode: how many documents are analysed at the same time. 1 keeps
    # memory use predictable on small machines (large dissertations queue up).
    MAX_CONCURRENT_ANALYSES: int = 1
    # Automatic retries of an interrupted/failed analysis (resumes from checkpoints).
    AUTO_RETRY_ATTEMPTS: int = 2
    RQ_QUEUE_NAME: str = "analysis"
    JOB_TIMEOUT_SECONDS: int = 60 * 60

    # --- storage ---
    STORAGE_DIR: Path = BASE_DIR / "data" / "uploads"
    MAX_UPLOAD_MB: int = 50
    MAX_FILES_PER_UPLOAD: int = 10
    MAX_DOCX_UNCOMPRESSED_MB: int = 300
    DELETE_FILES_AFTER_ANALYSIS: bool = False
    RETENTION_DAYS: int = 0  # 0 = keep until the user deletes
    CLAMAV_HOST: str = ""  # optional clamd host for malware scanning
    CLAMAV_PORT: int = 3310

    # --- OCR ---
    OCR_ENABLED: bool = True
    OCR_LANGUAGES: str = "uzb+rus+eng"
    OCR_MAX_PAGES: int = 400
    OCR_DPI: int = 250
    # Path to tesseract.exe on Windows if it is not on PATH (auto-detected when empty)
    TESSERACT_CMD: str = ""

    # --- bundled web UI (static export served by the backend; used by the Windows launcher)
    WEBUI_DIR: Path = BASE_DIR / "webui"

    # --- analysis ---
    SUSPICIOUS_THRESHOLD: float = 60.0
    QUICK_MAX_PASSAGES_PER_SECTION: int = 8
    EXTERNAL_MAX_PASSAGES: int = 40  # budget for DEEP analysis per document

    # --- external providers (all optional) ---
    AI_DETECTOR_API_URL: str = ""
    AI_DETECTOR_API_KEY: SecretStr = SecretStr("")
    AI_DETECTOR_NAME: str = "External AI detector"
    AI_DETECTOR_SCORE_FIELD: str = "ai_probability"
    AI_DETECTOR_SCORE_SCALE: float = 1.0  # 1.0 if the API returns 0..1, 100 if 0..100
    AI_DETECTOR_RPM: int = 30

    SIMILARITY_API_URL: str = ""
    SIMILARITY_API_KEY: SecretStr = SecretStr("")
    SIMILARITY_API_NAME: str = "External similarity service"
    SIMILARITY_RPM: int = 20

    ANTHROPIC_API_KEY: SecretStr = SecretStr("")
    ANTHROPIC_MODEL: str = "claude-haiku-4-5"  # lightest/cheapest Claude model
    OPENAI_API_KEY: SecretStr = SecretStr("")
    OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_REVIEW_ENABLED: bool = False  # LLM-assisted stylistic review is opt-in
    LLM_RPM: int = 20

    # --- plagiarism: reference corpus, paraphrase, internet ---
    ADMIN_EMAILS: str = ""  # comma list; the first registered user is always admin
    CORPUS_MAX_UPLOAD_MB: int = 60
    EMBEDDING_BACKEND: Literal["auto", "model2vec", "hash"] = "auto"
    EMBEDDING_MODEL: str = "minishlab/potion-multilingual-128M"
    MODEL_CACHE_DIR: Path = BASE_DIR / "data" / "models"
    PARAPHRASE_THRESHOLD_MODEL: float = 0.88  # cosine, model2vec vectors
    PARAPHRASE_THRESHOLD_HASH: float = 0.80  # cosine, hash vectors: paraphrase ~0.84, same-topic text <=0.74 in tests
    PARAPHRASE_CANDIDATE_DOCS: int = 30
    PLAGIARISM_MIN_SOURCE_WORDS: int = 12  # a source must cover at least this many words

    BRAVE_API_KEY: SecretStr = SecretStr("")
    BRAVE_API_URL: str = "https://api.search.brave.com/res/v1/web/search"
    BRAVE_PRICE_PER_1000_USD: float = 5.0  # check your Brave plan; used for the estimate only
    BRAVE_RPS: float = 1.0
    WEB_MAX_QUERIES: int = 40
    WEB_WORDS_PER_QUERY: int = 1500
    WEB_RESULTS_PER_QUERY: int = 3
    WEB_MAX_PAGE_MB: int = 5
    WEB_RESPECT_ROBOTS: bool = True
    WEB_PAGE_CACHE_DAYS: int = 30

    # harvesting open sources into the reference corpus
    HARVEST_OJS_URLS: str = ""  # comma list of OJS journal base URLs (…/index.php/<journal>)
    HARVEST_QUERIES: str = ""  # comma list of search queries for OpenAlex/CORE/Crossref/CyberLeninka
    HARVEST_MAX_PER_SOURCE: int = 50
    HARVEST_FETCH_FULLTEXT: bool = True
    HARVEST_MIN_TEXT_CHARS: int = 400
    HARVEST_RPS: float = 1.0
    OPENALEX_EMAIL: str = ""  # "polite pool" contact
    OPENALEX_FILTER: str = "is_oa:true"
    CORE_API_KEY: SecretStr = SecretStr("")
    CROSSREF_MAILTO: str = ""

    PROVIDER_TIMEOUT_SECONDS: float = 60.0
    PROVIDER_MAX_RETRIES: int = 3

    ui_default_language: str = Field(default="uz", alias="UI_DEFAULT_LANGUAGE")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


def csv_list(value: str) -> list[str]:
    return [x.strip() for x in value.replace("\n", ",").split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.ENV == "production":
        if settings.SECRET_KEY.get_secret_value().startswith("dev-insecure"):
            raise RuntimeError("SECRET_KEY must be set in production")
        if not settings.FILE_ENCRYPTION_KEY.get_secret_value():
            raise RuntimeError("FILE_ENCRYPTION_KEY must be set in production")
    return settings
