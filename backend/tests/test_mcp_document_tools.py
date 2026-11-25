from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from mcp import Client
from mcp.server import MCPServer

from app.core.services.document_storage import PresignedPost
from app.core.services.mcp_auth import MCPPrincipal
from app.mcp.document_tools import register_document_tools
from app.models import ActionOrigin, Document, DocumentStatus
from app.schemas.document import InitiateDocumentUploadInput


class FakeSessions:
    @asynccontextmanager
    async def session(self) -> AsyncIterator[object]:
        yield object()


class FakeDocuments:
    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.document = Document(
            id=5,
            business_id=11,
            project_id=3,
            uploaded_by_user_id=7,
            created_via=ActionOrigin.MCP,
            original_filename="report.pdf",
            declared_mime_type="application/pdf",
            detected_mime_type=None,
            declared_size=128,
            size_bytes=None,
            quarantine_key="businesses/11/quarantine/key",
            status=DocumentStatus.PENDING,
            upload_expires_at=now,
            created_at=now,
            updated_at=now,
        )

    async def initiate_upload(
        self,
        _session: object,
        _principal: MCPPrincipal,
        _data: InitiateDocumentUploadInput,
    ) -> tuple[Document, PresignedPost]:
        return self.document, PresignedPost(
            url="https://minio.example/upload",
            fields={"key": self.document.quarantine_key},
            expires_in=300,
        )

    async def finalize_upload(
        self, _session: object, _principal: MCPPrincipal, _document_id: int
    ) -> tuple[Document, bool]:
        self.document.status = DocumentStatus.AVAILABLE
        self.document.detected_mime_type = "application/pdf"
        self.document.size_bytes = 128
        self.document.content_sha256 = "a" * 64
        self.document.storage_key = "businesses/11/raw/sha256/aa/" + "a" * 64
        return self.document, False

    async def list_documents(
        self, *_args: object, **_kwargs: object
    ) -> tuple[list[Document], int]:
        return [self.document], 1

    async def get_document(self, *_args: object) -> Document:
        return self.document

    async def create_download_url(self, *_args: object) -> str:
        return "https://minio.example/download?signature=redacted"

    async def archive_document(self, *_args: object) -> bool:
        self.document.status = DocumentStatus.ARCHIVED
        return False


@pytest.mark.asyncio
async def test_document_tools_expose_upload_status_download_and_archive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = MCPServer("document-tools-test")
    documents = FakeDocuments()
    register_document_tools(
        server,
        FakeSessions(),  # type: ignore[arg-type]
        documents,  # type: ignore[arg-type]
        300,
    )
    principal = MCPPrincipal(
        user_id=7,
        business_id=11,
        scopes=frozenset({"documents:read", "documents:write"}),
        grant_id="grant-id",
    )
    monkeypatch.setattr(
        "app.mcp.document_tools.require_mcp_principal", lambda *_: principal
    )

    async with Client(server) as client:
        initiated = await client.call_tool(
            "initiate_document_upload",
            {
                "input": {
                    "filename": "report.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": 128,
                    "project_id": 3,
                }
            },
        )
        finalized = await client.call_tool(
            "finalize_document_upload", {"input": {"document_id": 5}}
        )
        listed = await client.call_tool("list_documents", {"input": {}})
        fetched = await client.call_tool("get_document", {"document_id": 5})
        download = await client.call_tool(
            "get_document_download_url", {"document_id": 5}
        )
        archived = await client.call_tool("archive_document", {"document_id": 5})

    assert initiated.structured_content["upload"] == {
        "method": "POST",
        "url": "https://minio.example/upload",
        "fields": {"key": "businesses/11/quarantine/key"},
        "expires_in": 300,
    }
    assert finalized.structured_content["document"]["content_sha256"] == "a" * 64
    assert finalized.structured_content["replayed"] is False
    assert listed.structured_content["total"] == 1
    assert fetched.structured_content["id"] == 5
    assert download.structured_content["expires_in"] == 300
    assert archived.structured_content == {
        "document_id": 5,
        "archived": True,
        "replayed": False,
    }
