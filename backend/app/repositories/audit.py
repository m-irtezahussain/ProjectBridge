from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionOrigin, AuditEvent


class AuditRepository:
    """Append and query audit events with mandatory tenant scoping."""

    def add(self, session: AsyncSession, event: AuditEvent) -> None:
        session.add(event)

    async def list_page(
        self,
        session: AsyncSession,
        business_id: int,
        *,
        interface: ActionOrigin | None,
        action: str | None,
        outcome: str | None,
        target_type: str | None,
        actor_user_id: int | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AuditEvent], int]:
        filters = [AuditEvent.business_id == business_id]
        if interface is not None:
            filters.append(AuditEvent.interface == interface)
        if action is not None:
            filters.append(AuditEvent.action == action)
        if outcome is not None:
            filters.append(AuditEvent.outcome == outcome)
        if target_type is not None:
            filters.append(AuditEvent.target_type == target_type)
        if actor_user_id is not None:
            filters.append(AuditEvent.actor_user_id == actor_user_id)
        if occurred_from is not None:
            filters.append(AuditEvent.occurred_at >= occurred_from)
        if occurred_to is not None:
            filters.append(AuditEvent.occurred_at <= occurred_to)
        items = list(
            await session.scalars(
                select(AuditEvent)
                .where(*filters)
                .order_by(AuditEvent.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        total = int(
            await session.scalar(
                select(func.count(AuditEvent.id)).where(*filters)
            )
            or 0
        )
        return items, total
