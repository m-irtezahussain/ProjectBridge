from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, event, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.provenance import ActionOrigin


class AuditEvent(Base):
    """Append-only, tenant-scoped record of a security-relevant action."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_business_id_id", "business_id", "id"),
        Index("ix_audit_events_business_action_id", "business_id", "action", "id"),
        Index(
            "ix_audit_events_business_target_id",
            "business_id",
            "target_type",
            "target_id",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("business.id", ondelete="RESTRICT"), nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    interface: Mapped[ActionOrigin] = mapped_column(
        SqlEnum(
            ActionOrigin,
            name="action_origin",
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False)
    details: Mapped[dict[str, object] | None] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def _reject_audit_mutation(*_args: object) -> None:
    raise TypeError("Audit events are append-only")
