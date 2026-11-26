from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActionOrigin, Document, DocumentAuditEvent, DocumentStatus


class DocumentRepository:
    """Document persistence with tenant scoping in every lookup."""

    def add(self, session: AsyncSession, document: Document) -> None:
        session.add(document)

    async def get(
        self,
        session: AsyncSession,
        business_id: int,
        document_id: int,
        *,
        include_archived: bool = False,
    ) -> Document | None:
        filters = [
            Document.id == document_id,
            Document.business_id == business_id,
        ]
        if not include_archived:
            filters.append(Document.archived_at.is_(None))
        return await session.scalar(select(Document).where(*filters))

    async def get_for_update(
        self,
        session: AsyncSession,
        business_id: int,
        document_id: int,
        *,
        include_archived: bool = False,
    ) -> Document | None:
        filters = [
            Document.id == document_id,
            Document.business_id == business_id,
        ]
        if not include_archived:
            filters.append(Document.archived_at.is_(None))
        return await session.scalar(
            select(Document).where(*filters).with_for_update()
        )

    async def find_by_hash(
        self,
        session: AsyncSession,
        business_id: int,
        sha256: str,
        *,
        exclude_document_id: int,
    ) -> Document | None:
        return await session.scalar(
            select(Document)
            .where(
                Document.business_id == business_id,
                Document.content_sha256 == sha256,
                Document.id != exclude_document_id,
                Document.storage_key.is_not(None),
            )
            .order_by(Document.id.asc())
            .limit(1)
        )

    async def list_page(
        self,
        session: AsyncSession,
        business_id: int,
        *,
        project_id: int | None,
        status: DocumentStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], int]:
        filters = [
            Document.business_id == business_id,
            Document.archived_at.is_(None),
        ]
        if project_id is not None:
            filters.append(Document.project_id == project_id)
        if status is not None:
            filters.append(Document.status == status)
        total = await session.scalar(
            select(func.count()).select_from(Document).where(*filters)
        )
        result = await session.scalars(
            select(Document)
            .where(*filters)
            .order_by(Document.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.all()), int(total or 0)

    async def list_before_id(
        self,
        session: AsyncSession,
        business_id: int,
        *,
        project_id: int | None,
        before_id: int | None,
        limit: int,
    ) -> list[Document]:
        filters = [
            Document.business_id == business_id,
            Document.archived_at.is_(None),
        ]
        if project_id is not None:
            filters.append(Document.project_id == project_id)
        if before_id is not None:
            filters.append(Document.id < before_id)
        result = await session.scalars(
            select(Document)
            .where(*filters)
            .order_by(Document.id.desc())
            .limit(limit)
        )
        return list(result.all())


class DocumentAuditRepository:
    def add(
        self,
        session: AsyncSession,
        *,
        document: Document,
        actor_user_id: int,
        action: str,
        outcome: str,
        actor_origin: ActionOrigin = ActionOrigin.MCP,
        details: dict[str, object] | None = None,
    ) -> None:
        session.add(
            DocumentAuditEvent(
                document_id=document.id,
                business_id=document.business_id,
                actor_user_id=actor_user_id,
                actor_origin=actor_origin,
                action=action,
                outcome=outcome,
                details=details,
            )
        )
