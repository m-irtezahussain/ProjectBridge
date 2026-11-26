from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings


class VectorStoreError(RuntimeError):
    pass


class VectorStoreUnavailableError(VectorStoreError):
    pass


@dataclass(frozen=True)
class VectorRecord:
    id: str
    document: str
    embedding: list[float]
    metadata: dict[str, str | int | float | bool]


@dataclass(frozen=True)
class VectorHit:
    id: str
    excerpt: str
    distance: float
    metadata: dict[str, object]


class ChromaVectorStore:
    """Tenant-separated Chroma v2 HTTP adapter with result-side isolation checks."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._base_url = settings.chroma_base_url
        self._tenant = settings.chroma_tenant
        self._database = settings.chroma_database
        self._prefix = self._sanitize_prefix(settings.chroma_collection_prefix)
        self._client_id = settings.chroma_cf_access_client_id
        self._client_secret = settings.chroma_cf_access_client_secret
        self._timeout = settings.chroma_timeout_seconds
        self._client = client

    @staticmethod
    def _sanitize_prefix(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9-]+", "-", value.casefold()).strip("-")
        return normalized[:32] or "projectbridge"

    def collection_name(self, business_id: int) -> str:
        return f"{self._prefix}-business-{business_id}"[:63].rstrip("-")

    def _headers(self) -> dict[str, str]:
        if (
            self._base_url is None
            or self._client_id is None
            or self._client_secret is None
        ):
            raise VectorStoreUnavailableError("Chroma vector store is not configured")
        return {
            "CF-Access-Client-Id": self._client_id,
            "CF-Access-Client-Secret": self._client_secret.get_secret_value(),
        }

    def _collections_url(self) -> str:
        if self._base_url is None:
            raise VectorStoreUnavailableError("Chroma vector store is not configured")
        return (
            f"{self._base_url.rstrip('/')}/api/v2/tenants/{quote(self._tenant, safe='')}"
            f"/databases/{quote(self._database, safe='')}/collections"
        )

    async def _request(
        self, method: str, url: str, *, json: object | None = None
    ) -> httpx.Response:
        try:
            if self._client is not None:
                response = await self._client.request(
                    method,
                    url,
                    headers=self._headers(),
                    timeout=self._timeout,
                    json=json,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(
                        method, url, headers=self._headers(), json=json
                    )
            response.raise_for_status()
            return response
        except httpx.HTTPError as error:
            raise VectorStoreError("Chroma request failed") from error

    async def _get_collection_id(
        self, business_id: int, *, create: bool
    ) -> str | None:
        name = self.collection_name(business_id)
        url = f"{self._collections_url()}/{quote(name, safe='')}"
        try:
            response = await self._request("GET", url)
        except VectorStoreError as error:
            cause = error.__cause__
            if not isinstance(cause, httpx.HTTPStatusError) or cause.response.status_code != 404:
                raise
            if not create:
                return None
            response = await self._request(
                "POST",
                self._collections_url(),
                json={
                    "name": name,
                    "get_or_create": True,
                    "metadata": {"hnsw:space": "cosine", "business_id": business_id},
                },
            )
        body = response.json()
        collection_id = body.get("id") if isinstance(body, dict) else None
        returned_name = body.get("name") if isinstance(body, dict) else None
        if returned_name is not None and returned_name != name:
            raise VectorStoreError("Chroma returned the wrong tenant collection")
        returned_metadata = body.get("metadata") if isinstance(body, dict) else None
        if (
            isinstance(returned_metadata, dict)
            and "business_id" in returned_metadata
            and returned_metadata.get("business_id") != business_id
        ):
            raise VectorStoreError("Chroma returned the wrong tenant collection")
        if not isinstance(collection_id, str) or not collection_id:
            raise VectorStoreError("Chroma returned an invalid collection")
        return collection_id

    async def upsert(self, business_id: int, records: list[VectorRecord]) -> None:
        if not records:
            return
        collection_id = await self._get_collection_id(business_id, create=True)
        assert collection_id is not None
        for record in records:
            if record.metadata.get("business_id") != business_id:
                raise VectorStoreError("Vector metadata does not match its business")
        await self._request(
            "POST",
            f"{self._collections_url()}/{quote(collection_id, safe='')}/upsert",
            json={
                "ids": [record.id for record in records],
                "embeddings": [record.embedding for record in records],
                "documents": [record.document for record in records],
                "metadatas": [record.metadata for record in records],
            },
        )

    async def delete(
        self,
        business_id: int,
        *,
        ids: list[str] | None = None,
        where: dict[str, object] | None = None,
    ) -> None:
        collection_id = await self._get_collection_id(business_id, create=False)
        if collection_id is None:
            return
        tenant_filter: dict[str, object] = {"business_id": {"$eq": business_id}}
        safe_where = (
            {"$and": [tenant_filter, where]} if where is not None else tenant_filter
        )
        payload: dict[str, object] = {"where": safe_where}
        if ids is not None:
            payload["ids"] = ids
        await self._request(
            "POST",
            f"{self._collections_url()}/{quote(collection_id, safe='')}/delete",
            json=payload,
        )

    async def query(
        self,
        business_id: int,
        embedding: list[float],
        *,
        limit: int,
        project_id: int | None,
        document_id: int | None,
    ) -> list[VectorHit]:
        collection_id = await self._get_collection_id(business_id, create=False)
        if collection_id is None:
            return []
        filters: list[dict[str, object]] = [
            {"business_id": {"$eq": business_id}}
        ]
        if project_id is not None:
            filters.append({"project_id": {"$eq": project_id}})
        if document_id is not None:
            filters.append({"document_id": {"$eq": document_id}})
        where: dict[str, object] = (
            filters[0] if len(filters) == 1 else {"$and": filters}
        )
        response = await self._request(
            "POST",
            f"{self._collections_url()}/{quote(collection_id, safe='')}/query",
            json={
                "query_embeddings": [embedding],
                "n_results": min(100, max(limit, limit * 3)),
                "where": where,
                "include": ["documents", "metadatas", "distances"],
            },
        )
        body = response.json()
        if not isinstance(body, dict):
            raise VectorStoreError("Chroma returned an invalid query result")
        ids = self._first_result_list(body.get("ids"))
        documents = self._first_result_list(body.get("documents"))
        metadatas = self._first_result_list(body.get("metadatas"))
        distances = self._first_result_list(body.get("distances"))
        hits: list[VectorHit] = []
        for item_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=False
        ):
            if not isinstance(metadata, dict) or metadata.get("business_id") != business_id:
                continue
            if project_id is not None and metadata.get("project_id") != project_id:
                continue
            if document_id is not None and metadata.get("document_id") != document_id:
                continue
            try:
                numeric_distance = float(distance)
            except (TypeError, ValueError):
                continue
            hits.append(
                VectorHit(
                    id=str(item_id),
                    excerpt=str(document)[:600],
                    distance=numeric_distance,
                    metadata={str(key): value for key, value in metadata.items()},
                )
            )
            if len(hits) >= limit:
                break
        return hits

    @staticmethod
    def _first_result_list(value: Any) -> list[Any]:
        if not isinstance(value, list) or not value or not isinstance(value[0], list):
            return []
        return value[0]
