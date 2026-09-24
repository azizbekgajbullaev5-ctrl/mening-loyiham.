"""Database entities.

Privacy note: full document text is never stored in the database. Only
metadata, scores, heading titles, and the text of passages that were flagged
(needed for the report) are persisted. Cross-document similarity uses hashed
fingerprints, not text.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    documents: Mapped[list[Document]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    doc_type: Mapped[str] = mapped_column(String(40), default="article")
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    keep_for_similarity: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    file_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    owner: Mapped[User] = relationship(back_populates="documents")
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version_no"
    )
    analyses: Mapped[list[Analysis]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="Analysis.created_at"
    )


class DocumentVersion(Base):
    """Extraction metadata + (possibly user-corrected) structure of a document."""

    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    pages_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    paragraph_count: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(10), default="unknown")
    language_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    language_distribution: Mapped[dict] = mapped_column(JSON, default=dict)
    is_scanned: Mapped[bool] = mapped_column(Boolean, default=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, default=False)
    structure: Mapped[list] = mapped_column(JSON, default=list)  # heading list
    structure_source: Mapped[str] = mapped_column(String(10), default="auto")
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    document: Mapped[Document] = relationship(back_populates="versions")


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str | None] = mapped_column(
        ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True
    )
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    depth: Mapped[str] = mapped_column(String(10), default="standard")
    status: Mapped[str] = mapped_column(String(12), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    message: Mapped[str] = mapped_column(String(300), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    document: Mapped[Document] = relationship(back_populates="analyses")
    version: Mapped[DocumentVersion | None] = relationship()
    result: Mapped[AnalysisResult | None] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", uselist=False
    )
    sections: Mapped[list[SectionResult]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="SectionResult.order"
    )
    passages: Mapped[list[PassageAnalysis]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="PassageAnalysis.paragraph_index"
    )
    similarity_matches: Mapped[list[SimilarityMatch]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    reports: Mapped[list[Report]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), unique=True)

    # AI-likelihood (local linguistic analysis). Estimate, not proof.
    ai_likelihood: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_confidence: Mapped[str] = mapped_column(String(8), default="low")
    ai_basis: Mapped[str] = mapped_column(String(40), default="local_linguistic")
    passages_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    passages_flagged: Mapped[int] = mapped_column(Integer, default=0)
    flagged_word_share: Mapped[float] = mapped_column(Float, default=0.0)

    # Similarity (separate measurement)
    similarity_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_internal: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_corpus: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_external: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity_scope: Mapped[str] = mapped_column(String(40), default="local_only")

    providers: Mapped[list] = mapped_column(JSON, default=list)
    provider_comparison: Mapped[dict] = mapped_column(JSON, default=dict)
    score_distribution: Mapped[list] = mapped_column(JSON, default=list)
    passage_positions: Mapped[list] = mapped_column(JSON, default=list)
    style: Mapped[dict] = mapped_column(JSON, default=dict)
    academic: Mapped[dict] = mapped_column(JSON, default=dict)
    paraphrase: Mapped[dict] = mapped_column(JSON, default=dict)
    repeated_phrases: Mapped[list] = mapped_column(JSON, default=list)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    methodology_version: Mapped[str] = mapped_column(String(20), default="1.0")

    analysis: Mapped[Analysis] = relationship(back_populates="result")


class SectionResult(Base):
    __tablename__ = "section_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer)
    parent_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    level: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(300))
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    ai_likelihood: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_confidence: Mapped[str | None] = mapped_column(String(8), nullable=True)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    suspicious_count: Mapped[int] = mapped_column(Integer, default=0)
    excluded_from_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    style_metrics: Mapped[dict] = mapped_column(JSON, default=dict)

    analysis: Mapped[Analysis] = relationship(back_populates="sections")


class PassageAnalysis(Base):
    """Only flagged (suspicious) passages are stored, including their text."""

    __tablename__ = "passage_analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    section_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapter_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int] = mapped_column(Integer)
    paragraph_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer)
    ai_likelihood: Mapped[float] = mapped_column(Float)
    confidence: Mapped[str] = mapped_column(String(8))
    characteristics: Mapped[list] = mapped_column(JSON, default=list)  # codes + values
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    provider_scores: Mapped[list] = mapped_column(JSON, default=list)

    analysis: Mapped[Analysis] = relationship(back_populates="passages")


class SimilarityMatch(Base):
    __tablename__ = "similarity_matches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    match_type: Mapped[str] = mapped_column(String(24))  # internal_duplicate|cross_document|paraphrase|external
    provider: Mapped[str] = mapped_column(String(60), default="local")
    section_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text, default="")
    matched_text: Mapped[str] = mapped_column(Text, default="")
    matched_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    matched_document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    matched_document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    similarity: Mapped[float] = mapped_column(Float)

    analysis: Mapped[Analysis] = relationship(back_populates="similarity_matches")


class DocumentFingerprint(Base):
    """Winnowed shingle hashes for same-owner cross-document similarity (no text)."""

    __tablename__ = "document_fingerprints"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)
    hash: Mapped[int] = mapped_column(BigInteger)
    paragraph_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("ix_fingerprint_owner_hash", "owner_id", "hash"),)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    owner_id: Mapped[str] = mapped_column(String(32), index=True)
    format: Mapped[str] = mapped_column(String(8))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    analysis: Mapped[Analysis] = relationship(back_populates="reports")


class ProviderCache(Base):
    """Cache of external provider results keyed by chunk hash (cost control)."""

    __tablename__ = "provider_cache"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(80))
    text_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("provider", "text_hash", name="uq_provider_cache"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(60))
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
