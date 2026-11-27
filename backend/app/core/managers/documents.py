import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.core.managers.projects import BusinessRequiredError, ProjectNotFoundError
from app.core.services.document_storage import (
    DocumentObjectNotFoundError,
    DocumentStorage,
    DocumentStorageError,
    PresignedPost,
)
from app.core.services.document_validation import (
    DocumentValidationError,
    DocumentValidationService,
)
from app.core.services.mcp_auth import AuthenticatedPrincipal
from app.core.services.mcp_mutations import (
    MutationVersionConflictError,
    completed_idempotency_replay,
    request_fingerprint,
)
from app.models import (
    Business,
    Document,
    DocumentStatus,
    SearchJobOperation,
)
from app.repositories.businesses import BusinessRepository
from app.repositories.documents import DocumentAuditRepository, DocumentRepository
from app.repositories.mcp_operations import MCPAuditRepository, MCPIdempotencyRepository
from app.repositories.projects import ProjectRepository
from app.repositories.search import SearchRepository
from app.schemas.document import InitiateDocumentUploadInput


class DocumentNotFoundError(ValueError):
    pass


class DocumentStateConflictError(ValueError):
    pass


class DocumentManager:
    """Tenant-safe orchestration for immutable document ingestion."""

    def __init__(
        self,
        settings: Settings,
        storage: DocumentStorage,
        businesses: BusinessRepository | None = None,
        projects: ProjectRepository | None = None,
        documents: DocumentRepository | None = None,
        document_audit: DocumentAuditRepository | None = None,
        mcp_audit: MCPAuditRepository | None = None,
        validation: DocumentValidationService | None = None,
        search: SearchRepository | None = None,
        idempotency: MCPIdempotencyRepository | None = None,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._businesses = businesses or BusinessRepository()
        self._projects = projects or ProjectRepository()
        self._documents = documents or DocumentRepository()
        self._document_audit = document_audit or DocumentAuditRepository()
        self._mcp_audit = mcp_audit or MCPAuditRepository()
        self._validation = validation or DocumentValidationService(settings)
        self._search = search or SearchRepository()
        self._idempotency = idempotency or MCPIdempotencyRepository()

    async def _require_business(
        self, session: AsyncSession, principal: AuthenticatedPrincipal
    ) -> Business:
        business = await self._businesses.get_for_owner(session, principal.user_id)
        if business is None or business.id != principal.business_id:
            raise BusinessRequiredError("Business registration required")
        return business

    async def initiate_upload(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        data: InitiateDocumentUploadInput,
    ) -> tuple[Document, PresignedPost]:
        await self._require_business(session, principal)
        if data.project_id is not None:
            project = await self._projects.get_active(
                session, principal.business_id, data.project_id
            )
            if project is None:
                raise ProjectNotFoundError("Project not found")
        safe_filename = self._validation.validate_declaration(
            data.filename,
            data.mime_type,
            data.size_bytes,
            self._settings.document_max_bytes,
        )
        quarantine_key = (
            f"businesses/{principal.business_id}/quarantine/{uuid4().hex}"
        )
        document = Document(
            business_id=principal.business_id,
            project_id=data.project_id,
            uploaded_by_user_id=principal.user_id,
            created_via=principal.origin,
            original_filename=safe_filename,
            declared_mime_type=data.mime_type,
            declared_size=data.size_bytes,
            quarantine_key=quarantine_key,
            status=DocumentStatus.PENDING,
            version=1,
            upload_expires_at=datetime.now(UTC)
            + timedelta(seconds=self._settings.s3_presign_expiry_seconds),
        )
        self._documents.add(session, document)
        await session.flush()
        try:
            upload = await self._storage.create_upload(
                quarantine_key, data.mime_type, data.size_bytes
            )
        except DocumentStorageError:
            document.status = DocumentStatus.FAILED
            document.failure_code = "storage_unavailable"
            document.failure_message = "Document storage is unavailable"
            self._document_audit.add(
                session,
                document=document,
                actor_user_id=principal.user_id,
                actor_origin=principal.origin,
                action="initiate",
                outcome="failed",
                details={"code": document.failure_code},
            )
            self._mcp_audit.add(
                session,
                principal=principal,
                tool_name="initiate_document_upload",
                target_type="document",
                target_id=document.id,
                outcome="storage_failed",
            )
            await session.commit()
            raise
        self._document_audit.add(
            session,
            document=document,
            actor_user_id=principal.user_id,
            actor_origin=principal.origin,
            action="initiate",
            outcome="success",
            details={"project_id": data.project_id},
        )
        self._mcp_audit.add(
            session,
            principal=principal,
            tool_name="initiate_document_upload",
            target_type="document",
            target_id=document.id,
            outcome="success",
        )
        await session.commit()
        await session.refresh(document)
        return document, upload

    async def finalize_upload(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        document_id: int,
    ) -> tuple[Document, bool]:
        await self._require_business(session, principal)
        document = await self._documents.get(
            session, principal.business_id, document_id
        )
        if document is None:
            raise DocumentNotFoundError("Document not found")
        if document.status in {DocumentStatus.AVAILABLE, DocumentStatus.DUPLICATE}:
            return document, True
        if document.status is DocumentStatus.ARCHIVED:
            raise DocumentNotFoundError("Document not found")
        if document.status is DocumentStatus.VALIDATING:
            raise DocumentStateConflictError("Document validation is already in progress")

        document.status = DocumentStatus.VALIDATING
        document.failure_code = None
        document.failure_message = None
        self._document_audit.add(
            session,
            document=document,
            actor_user_id=principal.user_id,
            actor_origin=principal.origin,
            action="finalize",
            outcome="started",
        )
        await session.commit()

        try:
            head = await self._storage.head(document.quarantine_key)
            if head.size_bytes != document.declared_size:
                raise DocumentValidationError(
                    "size_mismatch", "Uploaded size does not match the declared size"
                )
            if head.size_bytes > self._settings.document_max_bytes:
                raise DocumentValidationError(
                    "size_limit", "Uploaded document exceeds the size limit"
                )
            if head.content_type != document.declared_mime_type:
                raise DocumentValidationError(
                    "content_type_mismatch",
                    "Uploaded content type does not match the declaration",
                )
            with tempfile.TemporaryDirectory(prefix="projectbridge-document-") as temp_dir:
                path = Path(temp_dir) / "raw-upload"
                downloaded = await self._storage.download_to_path(
                    document.quarantine_key,
                    path,
                    self._settings.document_max_bytes,
                )
                if downloaded.size_bytes != head.size_bytes:
                    raise DocumentValidationError(
                        "size_mismatch", "Uploaded object changed during validation"
                    )
                validated = await asyncio.to_thread(
                    self._validation.validate_file,
                    path,
                    document.declared_mime_type,
                )
            current = await self._storage.head(document.quarantine_key)
            if current.size_bytes != head.size_bytes or current.etag != head.etag:
                raise DocumentValidationError(
                    "object_changed", "Uploaded object changed during validation"
                )

            immutable_key = (
                f"businesses/{principal.business_id}/raw/sha256/"
                f"{downloaded.sha256[:2]}/{downloaded.sha256}"
            )
            duplicate = await self._documents.find_by_hash(
                session,
                principal.business_id,
                downloaded.sha256,
                exclude_document_id=document.id,
            )
            if not await self._storage.exists(immutable_key):
                await self._storage.copy_immutable(
                    document.quarantine_key,
                    immutable_key,
                    current.etag,
                    validated.mime_type,
                    document.original_filename,
                    downloaded.sha256,
                )
            promoted = await self._storage.head(immutable_key)
            if (
                promoted.size_bytes != downloaded.size_bytes
                or promoted.content_sha256 != downloaded.sha256
            ):
                raise DocumentStorageError("Immutable object verification failed")

            document.detected_mime_type = validated.mime_type
            document.size_bytes = downloaded.size_bytes
            document.content_sha256 = downloaded.sha256
            document.storage_key = immutable_key
            document.duplicate_of_document_id = duplicate.id if duplicate else None
            document.status = (
                DocumentStatus.DUPLICATE if duplicate else DocumentStatus.AVAILABLE
            )
            self._document_audit.add(
                session,
                document=document,
                actor_user_id=principal.user_id,
                actor_origin=principal.origin,
                action="finalize",
                outcome="duplicate" if duplicate else "success",
                details={
                    "sha256": downloaded.sha256,
                    "page_count": validated.page_count,
                    "width": validated.width,
                    "height": validated.height,
                },
            )
            self._mcp_audit.add(
                session,
                principal=principal,
                tool_name="finalize_document_upload",
                target_type="document",
                target_id=document.id,
                outcome="duplicate" if duplicate else "success",
            )
            await session.commit()
        except DocumentValidationError as error:
            await self._record_failure(
                session,
                principal,
                document,
                code=error.code,
                message=str(error),
                outcome="validation_failed",
            )
            raise
        except DocumentObjectNotFoundError as error:
            await self._record_failure(
                session,
                principal,
                document,
                code="object_not_found",
                message="Uploaded object was not found",
                outcome="not_found",
            )
            raise DocumentStateConflictError("Uploaded object was not found") from error
        except DocumentStorageError:
            await self._record_failure(
                session,
                principal,
                document,
                code="storage_error",
                message="Document storage validation failed",
                outcome="storage_failed",
            )
            raise

        try:
            await self._storage.delete_quarantine(document.quarantine_key)
        except DocumentStorageError:
            self._document_audit.add(
                session,
                document=document,
                actor_user_id=principal.user_id,
                actor_origin=principal.origin,
                action="quarantine_cleanup",
                outcome="failed",
            )
            await session.commit()
        await session.refresh(document)
        return document, False

    async def _record_failure(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        document: Document,
        *,
        code: str,
        message: str,
        outcome: str,
    ) -> None:
        document.status = DocumentStatus.FAILED
        document.failure_code = code
        document.failure_message = message[:500]
        self._document_audit.add(
            session,
            document=document,
            actor_user_id=principal.user_id,
            actor_origin=principal.origin,
            action="finalize",
            outcome=outcome,
            details={"code": code},
        )
        self._mcp_audit.add(
            session,
            principal=principal,
            tool_name="finalize_document_upload",
            target_type="document",
            target_id=document.id,
            outcome=outcome,
        )
        await session.commit()

    async def list_documents(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        *,
        project_id: int | None,
        status: DocumentStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Document], int]:
        await self._require_business(session, principal)
        if project_id is not None:
            project = await self._projects.get_active(
                session, principal.business_id, project_id
            )
            if project is None:
                raise ProjectNotFoundError("Project not found")
        return await self._documents.list_page(
            session,
            principal.business_id,
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def get_document(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        document_id: int,
    ) -> Document:
        await self._require_business(session, principal)
        document = await self._documents.get(
            session, principal.business_id, document_id
        )
        if document is None:
            raise DocumentNotFoundError("Document not found")
        return document

    async def create_download_url(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        document_id: int,
    ) -> str:
        document = await self.get_document(session, principal, document_id)
        if document.status not in {
            DocumentStatus.AVAILABLE,
            DocumentStatus.DUPLICATE,
        } or document.storage_key is None:
            raise DocumentStateConflictError("Document is not available for download")
        url = await self._storage.create_download_url(
            document.storage_key, document.original_filename
        )
        self._document_audit.add(
            session,
            document=document,
            actor_user_id=principal.user_id,
            actor_origin=principal.origin,
            action="download_url",
            outcome="success",
        )
        await session.commit()
        return url

    async def archive_document(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        document_id: int,
        expected_version: int,
        idempotency_key: str,
    ) -> bool:
        await self._require_business(session, principal)
        tool_name = "archive_document"
        fingerprint = request_fingerprint(
            tool_name,
            {"document_id": document_id, "expected_version": expected_version},
        )
        claim = await self._idempotency.claim(
            session,
            principal=principal,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            fingerprint=fingerprint,
        )
        replay = completed_idempotency_replay(
            claim, fingerprint=fingerprint, result_type="document_archive"
        )
        if replay is not None:
            self._mcp_audit.add(
                session,
                principal=principal,
                tool_name=tool_name,
                target_type="document",
                target_id=document_id,
                outcome="idempotent_replay",
            )
            await session.commit()
            return True
        document = await self._documents.get_for_update(
            session,
            principal.business_id,
            document_id,
            include_archived=True,
        )
        if document is None:
            await session.rollback()
            raise DocumentNotFoundError("Document not found")
        replayed = document.archived_at is not None
        if not replayed:
            if document.version != expected_version:
                await session.rollback()
                raise MutationVersionConflictError(
                    f"Document version conflict: expected {expected_version}, "
                    f"current {document.version}"
                )
            document.archived_at = datetime.now(UTC)
            document.status = DocumentStatus.ARCHIVED
            document.version += 1
            await self._search.enqueue(
                session,
                business_id=principal.business_id,
                project_id=document.project_id,
                document_id=document.id,
                operation=SearchJobOperation.DELETE_DOCUMENT,
                max_attempts=self._settings.rag_max_attempts,
            )
        self._idempotency.complete(
            claim.record,
            result_type="document_archive",
            result_id=document.id,
            response_body={"archived": True, "version": document.version},
        )
        self._document_audit.add(
            session,
            document=document,
            actor_user_id=principal.user_id,
            actor_origin=principal.origin,
            action="archive",
            outcome="idempotent_replay" if replayed else "success",
        )
        self._mcp_audit.add(
            session,
            principal=principal,
            tool_name=tool_name,
            target_type="document",
            target_id=document.id,
            outcome="idempotent_replay" if replayed else "success",
        )
        await session.commit()
        return replayed
