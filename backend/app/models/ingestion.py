from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.provenance import ActionOrigin


class IngestionStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class CandidateStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CREATED = "created"
    FAILED = "failed"


class DocumentText(Base):
    __tablename__ = "document_texts"
    __table_args__ = (
        UniqueConstraint("ingestion_run_id", name="uq_document_text_ingestion_run"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("document_ingestion_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    engine: Mapped[str] = mapped_column(String(50), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    average_confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[StageStatus] = mapped_column(
        SqlEnum(
            StageStatus,
            name="ingestion_stage_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=StageStatus.COMPLETED,
        server_default=StageStatus.COMPLETED.value,
    )
    created_via: Mapped[ActionOrigin] = mapped_column(
        SqlEnum(
            ActionOrigin,
            name="action_origin",
            values_callable=lambda origins: [origin.value for origin in origins],
        ),
        nullable=False,
        default=ActionOrigin.WORKER,
        server_default=ActionOrigin.WORKER.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class IngestionRun(Base):
    __tablename__ = "document_ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    initiated_via: Mapped[ActionOrigin] = mapped_column(
        SqlEnum(
            ActionOrigin,
            name="action_origin",
            values_callable=lambda origins: [origin.value for origin in origins],
        ),
        nullable=False,
        default=ActionOrigin.MCP,
        server_default=ActionOrigin.MCP.value,
    )
    grant_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[IngestionStatus] = mapped_column(
        SqlEnum(
            IngestionStatus,
            name="ingestion_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=IngestionStatus.QUEUED,
        server_default=IngestionStatus.QUEUED.value,
        index=True,
    )
    ocr_status: Mapped[StageStatus] = mapped_column(
        SqlEnum(
            StageStatus,
            name="ingestion_stage_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=StageStatus.PENDING,
        server_default=StageStatus.PENDING.value,
    )
    extraction_status: Mapped[StageStatus] = mapped_column(
        SqlEnum(
            StageStatus,
            name="ingestion_stage_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=StageStatus.PENDING,
        server_default=StageStatus.PENDING.value,
    )
    task_status: Mapped[StageStatus] = mapped_column(
        SqlEnum(
            StageStatus,
            name="ingestion_stage_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=StageStatus.PENDING,
        server_default=StageStatus.PENDING.value,
    )
    indexing_status: Mapped[StageStatus] = mapped_column(
        SqlEnum(
            StageStatus,
            name="ingestion_stage_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=StageStatus.PENDING,
        server_default=StageStatus.PENDING.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(100))
    last_error_stage: Mapped[str | None] = mapped_column(String(50))
    last_error_code: Mapped[str | None] = mapped_column(String(100))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskCandidate(Base):
    __tablename__ = "document_task_candidates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("document_ingestion_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    source_text_id: Mapped[int] = mapped_column(
        ForeignKey("document_texts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    source_excerpt: Mapped[str] = mapped_column(String(500), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    source_line_start: Mapped[int | None] = mapped_column(Integer)
    source_line_end: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    extractor: Mapped[str] = mapped_column(String(100), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(50), nullable=False)
    extracted_via: Mapped[ActionOrigin] = mapped_column(
        SqlEnum(
            ActionOrigin,
            name="action_origin",
            values_callable=lambda origins: [origin.value for origin in origins],
        ),
        nullable=False,
        default=ActionOrigin.WORKER,
        server_default=ActionOrigin.WORKER.value,
    )
    status: Mapped[CandidateStatus] = mapped_column(
        SqlEnum(
            CandidateStatus,
            name="task_candidate_status",
            values_callable=lambda values: [v.value for v in values],
        ),
        nullable=False,
        default=CandidateStatus.PENDING,
        server_default=CandidateStatus.PENDING.value,
        index=True,
    )
    created_task_id: Mapped[int | None] = mapped_column(Integer)
    failure_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DocumentSearchChunk(Base):
    __tablename__ = "document_search_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_search_chunk_index"),
        Index("ix_document_search_chunks_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(content, ''))", persisted=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IngestionEvent(Base):
    """Append-only provenance for user- and worker-driven ingestion actions."""

    __tablename__ = "document_ingestion_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ingestion_run_id: Mapped[int] = mapped_column(
        ForeignKey("document_ingestion_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    origin: Mapped[ActionOrigin] = mapped_column(
        SqlEnum(
            ActionOrigin,
            name="action_origin",
            values_callable=lambda origins: [origin.value for origin in origins],
        ),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    stage: Mapped[str | None] = mapped_column(String(50))
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    worker_id: Mapped[str | None] = mapped_column(String(100))
    details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
