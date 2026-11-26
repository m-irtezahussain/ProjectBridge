from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.provenance import ActionOrigin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.task import Task


class DocumentStatus(StrEnum):
    PENDING = "pending"
    VALIDATING = "validating"
    AVAILABLE = "available"
    DUPLICATE = "duplicate"
    FAILED = "failed"
    ARCHIVED = "archived"


class Document(Base):
    """Tenant-owned metadata for an immutable raw object."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("declared_size > 0", name="ck_documents_declared_size_positive"),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes > 0",
            name="ck_documents_size_bytes_positive",
        ),
        CheckConstraint("version > 0", name="ck_documents_version_positive"),
        Index(
            "ix_documents_business_active_id_desc",
            "business_id",
            "id",
            postgresql_where=text("archived_at IS NULL"),
        ),
        Index(
            "ix_documents_business_project_active_id_desc",
            "business_id",
            "project_id",
            "id",
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_via: Mapped[ActionOrigin] = mapped_column(
        SqlEnum(
            ActionOrigin,
            name="action_origin",
            values_callable=lambda origins: [origin.value for origin in origins],
        ),
        nullable=False,
        default=ActionOrigin.MCP,
        server_default=ActionOrigin.MCP.value,
    )
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    declared_mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detected_mime_type: Mapped[str | None] = mapped_column(String(100))
    declared_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    quarantine_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), index=True)
    status: Mapped[DocumentStatus] = mapped_column(
        SqlEnum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda statuses: [status.value for status in statuses],
            validate_strings=True,
        ),
        nullable=False,
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
        index=True,
    )
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    duplicate_of_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    upload_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    __mapper_args__ = {"version_id_col": version}

    project: Mapped[Project | None] = relationship(
        back_populates="documents", lazy="raise"
    )
    source_tasks: Mapped[list[Task]] = relationship(
        back_populates="source_document", lazy="raise"
    )


class DocumentAuditEvent(Base):
    """Append-only history of document lifecycle changes."""

    __tablename__ = "document_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_origin: Mapped[ActionOrigin] = mapped_column(
        SqlEnum(
            ActionOrigin,
            name="action_origin",
            values_callable=lambda origins: [origin.value for origin in origins],
        ),
        nullable=False,
        default=ActionOrigin.MCP,
        server_default=ActionOrigin.MCP.value,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
