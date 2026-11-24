import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from app.core.managers.documents import DocumentManager, DocumentNotFoundError
from app.core.services.document_storage import (
    DownloadedObject,
    ObjectMetadata,
    PresignedPost,
)
from app.core.services.document_validation import DocumentValidationError
from app.core.services.mcp_auth import MCPPrincipal
from app.models import Business, Document, DocumentStatus, Project, ProjectStatus
from app.schemas.document import InitiateDocumentUploadInput
from tests.test_document_validation import png_bytes


class FakeBusinesses:
    async def get_for_owner(self, _session: object, owner_id: int) -> Business | None:
        if owner_id == 7:
            return Business(id=11, name="Acme", owned_by=7)
        return None


class FakeProjects:
    async def get_active(
        self, _session: object, business_id: int, project_id: int
    ) -> Project | None:
        if business_id == 11 and project_id == 3:
            return Project(
                id=3,
                name="Portal",
                business_id=11,
                status=ProjectStatus.ACTIVE,
            )
        return None


class FakeDocuments:
    def __init__(self) -> None:
        self.items: dict[int, Document] = {}

    def add(self, _session: object, document: Document) -> None:
        document.id = len(self.items) + 1
        now = datetime.now(UTC)
        document.created_at = now
        document.updated_at = now
        self.items[document.id] = document

    async def get(
        self,
        _session: object,
        business_id: int,
        document_id: int,
        *,
        include_archived: bool = False,
    ) -> Document | None:
        document = self.items.get(document_id)
        if document is None or document.business_id != business_id:
            return None
        if document.archived_at is not None and not include_archived:
            return None
        return document

    async def find_by_hash(
        self,
        _session: object,
        business_id: int,
        sha256: str,
        *,
        exclude_document_id: int,
    ) -> Document | None:
        return next(
            (
                document
                for document in self.items.values()
                if document.business_id == business_id
                and document.id != exclude_document_id
                and document.content_sha256 == sha256
                and document.storage_key is not None
            ),
            None,
        )

    async def list_page(
        self, _session: object, business_id: int, **_kwargs: object
    ) -> tuple[list[Document], int]:
        items = [
            item
            for item in self.items.values()
            if item.business_id == business_id and item.archived_at is None
        ]
        return items, len(items)


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def add(self, _session: object, **event: object) -> None:
        self.events.append(event)


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def create_upload(
        self, key: str, mime_type: str, exact_size: int
    ) -> PresignedPost:
        return PresignedPost(
            url="https://minio.example/upload",
            fields={"key": key, "Content-Type": mime_type},
            expires_in=300,
        )

    async def head(self, key: str) -> ObjectMetadata:
        data = self.objects[key]
        return ObjectMetadata(
            size_bytes=len(data),
            etag=hashlib.md5(data, usedforsecurity=False).hexdigest(),
            content_type="image/png",
            content_sha256=(
                hashlib.sha256(data).hexdigest()
                if "/raw/sha256/" in key
                else None
            ),
        )

    async def download_to_path(
        self, key: str, destination: Path, max_bytes: int
    ) -> DownloadedObject:
        data = self.objects[key]
        assert len(data) <= max_bytes
        await asyncio.to_thread(destination.write_bytes, data)
        return DownloadedObject(
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            etag=hashlib.md5(data, usedforsecurity=False).hexdigest(),
        )

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def copy_immutable(
        self,
        source_key: str,
        destination_key: str,
        source_etag: str,
        mime_type: str,
        filename: str,
        sha256: str,
    ) -> None:
        self.objects[destination_key] = self.objects[source_key]

    async def delete_quarantine(self, key: str) -> None:
        self.objects.pop(key, None)

    async def create_download_url(self, key: str, filename: str) -> str:
        return f"https://minio.example/{key}?download={filename}"


def principal(business_id: int = 11) -> MCPPrincipal:
    return MCPPrincipal(
        user_id=7,
        business_id=business_id,
        scopes=frozenset({"documents:read", "documents:write"}),
        grant_id="grant-id",
    )


def make_manager() -> tuple[DocumentManager, FakeDocuments, FakeStorage, FakeAudit]:
    settings = Settings()
    documents = FakeDocuments()
    storage = FakeStorage()
    audit = FakeAudit()
    manager = DocumentManager(
        settings,
        storage,
        FakeBusinesses(),  # type: ignore[arg-type]
        FakeProjects(),  # type: ignore[arg-type]
        documents,  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
        audit,  # type: ignore[arg-type]
    )
    return manager, documents, storage, audit


async def initiate_png(
    manager: DocumentManager,
    storage: FakeStorage,
    session: AsyncMock,
    filename: str = "../scan.png",
) -> Document:
    data = png_bytes()
    document, upload = await manager.initiate_upload(
        session,
        principal(),
        InitiateDocumentUploadInput(
            filename=filename,
            mime_type="image/png",
            size_bytes=len(data),
            project_id=3,
        ),
    )
    assert upload.fields["key"] == document.quarantine_key
    storage.objects[document.quarantine_key] = data
    return document


async def test_finalize_promotes_by_tenant_hash_and_handles_duplicates() -> None:
    manager, _documents, storage, audit = make_manager()
    session = AsyncMock()
    first = await initiate_png(manager, storage, session)

    finalized, replayed = await manager.finalize_upload(session, principal(), first.id)
    replay, was_replayed = await manager.finalize_upload(
        session, principal(), first.id
    )
    second = await initiate_png(manager, storage, session, "duplicate.png")
    duplicate, duplicate_replayed = await manager.finalize_upload(
        session, principal(), second.id
    )

    expected_hash = hashlib.sha256(png_bytes()).hexdigest()
    assert finalized.status is DocumentStatus.AVAILABLE
    assert finalized.content_sha256 == expected_hash
    assert finalized.storage_key == f"businesses/11/raw/sha256/{expected_hash[:2]}/{expected_hash}"
    assert finalized.original_filename == "scan.png"
    assert replayed is False
    assert replay is finalized
    assert was_replayed is True
    assert duplicate.status is DocumentStatus.DUPLICATE
    assert duplicate.duplicate_of_document_id == first.id
    assert duplicate_replayed is False
    assert any(event.get("outcome") == "duplicate" for event in audit.events)


async def test_validation_failure_is_reported_and_quarantine_is_retained() -> None:
    manager, _documents, storage, _audit = make_manager()
    session = AsyncMock()
    document = await initiate_png(manager, storage, session)
    storage.objects[document.quarantine_key] = b"not really a png".ljust(
        document.declared_size, b"!"
    )

    with pytest.raises(DocumentValidationError):
        await manager.finalize_upload(session, principal(), document.id)

    assert document.status is DocumentStatus.FAILED
    assert document.failure_code == "mime_mismatch"
    assert document.quarantine_key in storage.objects


async def test_tenant_isolation_and_idempotent_archive() -> None:
    manager, documents, storage, _audit = make_manager()
    session = AsyncMock()
    document = await initiate_png(manager, storage, session)

    other_tenant = Document(
        id=99,
        business_id=999,
        uploaded_by_user_id=99,
        original_filename="secret.png",
        declared_mime_type="image/png",
        declared_size=10,
        quarantine_key="businesses/999/quarantine/secret",
        status=DocumentStatus.PENDING,
        upload_expires_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    documents.items[99] = other_tenant
    with pytest.raises(DocumentNotFoundError):
        await manager.get_document(session, principal(), other_tenant.id)

    first = await manager.archive_document(session, principal(), document.id)
    replay = await manager.archive_document(session, principal(), document.id)

    assert first is False
    assert replay is True
    assert document.status is DocumentStatus.ARCHIVED
