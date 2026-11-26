from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SearchJobOperation(StrEnum):
    UPSERT_DOCUMENT = "upsert_document"
    DELETE_DOCUMENT = "delete_document"
    UPSERT_TASK = "upsert_task"
    DELETE_TASK = "delete_task"
    DELETE_PROJECT = "delete_project"
    REINDEX_PROJECT = "reindex_project"


class SearchJobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchIndexJob(Base):
    """Durable, tenant-scoped synchronization request for the vector index."""

    __tablename__ = "search_index_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    operation: Mapped[SearchJobOperation] = mapped_column(
        SqlEnum(
            SearchJobOperation,
            name="search_job_operation",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[SearchJobStatus] = mapped_column(
        SqlEnum(
            SearchJobStatus,
            name="search_job_status",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=SearchJobStatus.QUEUED,
        server_default=SearchJobStatus.QUEUED.value,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
