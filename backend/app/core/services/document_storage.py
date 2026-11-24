from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, Protocol
from urllib.parse import quote

import aioboto3  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from app.config import Settings


class DocumentStorageError(RuntimeError):
    pass


class DocumentObjectNotFoundError(DocumentStorageError):
    pass


@dataclass(frozen=True)
class PresignedPost:
    url: str
    fields: dict[str, str]
    expires_in: int


@dataclass(frozen=True)
class ObjectMetadata:
    size_bytes: int
    etag: str
    content_type: str | None
    content_sha256: str | None


@dataclass(frozen=True)
class DownloadedObject:
    size_bytes: int
    sha256: str
    etag: str


class DocumentStorage(Protocol):
    async def create_upload(
        self, key: str, mime_type: str, exact_size: int
    ) -> PresignedPost: ...

    async def head(self, key: str) -> ObjectMetadata: ...

    async def download_to_path(
        self, key: str, destination: Path, max_bytes: int
    ) -> DownloadedObject: ...

    async def exists(self, key: str) -> bool: ...

    async def copy_immutable(
        self,
        source_key: str,
        destination_key: str,
        source_etag: str,
        mime_type: str,
        filename: str,
        sha256: str,
    ) -> None: ...

    async def delete_quarantine(self, key: str) -> None: ...

    async def create_download_url(self, key: str, filename: str) -> str: ...


class UnavailableDocumentStorage:
    """Fail closed when optional development storage settings are absent."""

    @staticmethod
    def _raise() -> NoReturn:
        raise DocumentStorageError("Document storage is not configured")

    async def create_upload(
        self, key: str, mime_type: str, exact_size: int
    ) -> PresignedPost:
        self._raise()

    async def head(self, key: str) -> ObjectMetadata:
        self._raise()

    async def download_to_path(
        self, key: str, destination: Path, max_bytes: int
    ) -> DownloadedObject:
        self._raise()

    async def exists(self, key: str) -> bool:
        self._raise()

    async def copy_immutable(
        self,
        source_key: str,
        destination_key: str,
        source_etag: str,
        mime_type: str,
        filename: str,
        sha256: str,
    ) -> None:
        self._raise()

    async def delete_quarantine(self, key: str) -> None:
        self._raise()

    async def create_download_url(self, key: str, filename: str) -> str:
        self._raise()


class S3DocumentStorage:
    """Private S3-compatible storage for quarantine and immutable raw objects."""

    def __init__(self, settings: Settings) -> None:
        if (
            settings.s3_endpoint_url is None
            or settings.s3_access_key_id is None
            or settings.s3_secret_access_key is None
            or settings.s3_bucket is None
        ):
            raise DocumentStorageError("Document storage is not configured")
        self._endpoint_url = settings.s3_endpoint_url
        self._access_key = settings.s3_access_key_id
        self._secret_key = settings.s3_secret_access_key.get_secret_value()
        self._bucket = settings.s3_bucket
        self._region = settings.s3_region
        self._expiry = settings.s3_presign_expiry_seconds
        self._session = aioboto3.Session()
        self._config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.s3_use_path_style else "virtual"},
            retries={"max_attempts": 3, "mode": "standard"},
        )

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            config=self._config,
        ) as client:
            yield client

    async def create_upload(
        self, key: str, mime_type: str, exact_size: int
    ) -> PresignedPost:
        async with self._client() as client:
            result = await client.generate_presigned_post(
                Bucket=self._bucket,
                Key=key,
                Fields={"Content-Type": mime_type},
                Conditions=[
                    {"Content-Type": mime_type},
                    ["content-length-range", exact_size, exact_size],
                ],
                ExpiresIn=self._expiry,
            )
        fields = result.get("fields")
        url = result.get("url")
        if not isinstance(url, str) or not isinstance(fields, dict):
            raise DocumentStorageError("Object storage returned an invalid upload policy")
        return PresignedPost(
            url=url,
            fields={str(name): str(value) for name, value in fields.items()},
            expires_in=self._expiry,
        )

    async def head(self, key: str) -> ObjectMetadata:
        try:
            async with self._client() as client:
                result = await client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404 or error.response.get("Error", {}).get("Code") in {
                "NoSuchKey",
                "NotFound",
            }:
                raise DocumentObjectNotFoundError("Uploaded object was not found") from error
            raise DocumentStorageError("Object storage request failed") from error
        return ObjectMetadata(
            size_bytes=int(result["ContentLength"]),
            etag=str(result.get("ETag", "")).strip('"'),
            content_type=(
                str(result["ContentType"]) if result.get("ContentType") else None
            ),
            content_sha256=(
                str(result["Metadata"].get("sha256"))
                if isinstance(result.get("Metadata"), dict)
                and result["Metadata"].get("sha256")
                else None
            ),
        )

    async def download_to_path(
        self, key: str, destination: Path, max_bytes: int
    ) -> DownloadedObject:
        digest = hashlib.sha256()
        total = 0
        try:
            async with self._client() as client:
                response = await client.get_object(Bucket=self._bucket, Key=key)
                etag = str(response.get("ETag", "")).strip('"')
                body = response["Body"]
                with destination.open("wb") as file:
                    while chunk := await body.read(64 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            raise DocumentStorageError("Uploaded object exceeds the size limit")
                        digest.update(chunk)
                        file.write(chunk)
        except DocumentStorageError:
            raise
        except ClientError as error:
            raise DocumentStorageError("Object storage download failed") from error
        return DownloadedObject(
            size_bytes=total,
            sha256=digest.hexdigest(),
            etag=etag,
        )

    async def exists(self, key: str) -> bool:
        try:
            await self.head(key)
        except DocumentObjectNotFoundError:
            return False
        return True

    async def copy_immutable(
        self,
        source_key: str,
        destination_key: str,
        source_etag: str,
        mime_type: str,
        filename: str,
        sha256: str,
    ) -> None:
        disposition = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
        try:
            async with self._client() as client:
                await client.copy_object(
                    Bucket=self._bucket,
                    Key=destination_key,
                    CopySource={"Bucket": self._bucket, "Key": source_key},
                    CopySourceIfMatch=source_etag,
                    MetadataDirective="REPLACE",
                    Metadata={"sha256": sha256},
                    ContentType=mime_type,
                    ContentDisposition=disposition,
                )
        except ClientError as error:
            raise DocumentStorageError("Immutable object promotion failed") from error

    async def delete_quarantine(self, key: str) -> None:
        try:
            async with self._client() as client:
                await client.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            raise DocumentStorageError("Quarantine cleanup failed") from error

    async def create_download_url(self, key: str, filename: str) -> str:
        disposition = f"attachment; filename*=UTF-8''{quote(filename, safe='')}"
        async with self._client() as client:
            return str(
                await client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self._bucket,
                        "Key": key,
                        "ResponseContentDisposition": disposition,
                        "ResponseCacheControl": "private, no-store",
                    },
                    ExpiresIn=self._expiry,
                )
            )
