from __future__ import annotations

import math
from typing import Protocol

import httpx

from app.config import Settings


class EmbeddingServiceError(RuntimeError):
    pass


class EmbeddingServiceUnavailableError(EmbeddingServiceError):
    pass


class EmbeddingService(Protocol):
    @property
    def model(self) -> str: ...

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingService:
    """Ollama `/api/embed` adapter. Inputs are data, never executable instructions."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_embedding_model
        self._timeout = settings.ollama_timeout_seconds
        self._client = client

    @property
    def model(self) -> str:
        return self._model or "unconfigured"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._base_url is None or self._model is None:
            raise EmbeddingServiceUnavailableError(
                "Ollama embedding service is not configured"
            )
        payload = {"model": self._model, "input": texts, "truncate": True}
        try:
            if self._client is not None:
                response = await self._client.post(
                    f"{self._base_url.rstrip('/')}/api/embed",
                    json=payload,
                    timeout=self._timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        f"{self._base_url.rstrip('/')}/api/embed", json=payload
                    )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise EmbeddingServiceError("Ollama embedding request failed") from error
        raw_embeddings = body.get("embeddings") if isinstance(body, dict) else None
        if not isinstance(raw_embeddings, list) or len(raw_embeddings) != len(texts):
            raise EmbeddingServiceError("Ollama returned an invalid embedding count")
        embeddings: list[list[float]] = []
        expected_dimensions: int | None = None
        for raw_embedding in raw_embeddings:
            if not isinstance(raw_embedding, list) or not raw_embedding:
                raise EmbeddingServiceError("Ollama returned an invalid embedding")
            try:
                embedding = [float(value) for value in raw_embedding]
            except (TypeError, ValueError) as error:
                raise EmbeddingServiceError("Ollama returned a non-numeric embedding") from error
            if not all(math.isfinite(value) for value in embedding):
                raise EmbeddingServiceError("Ollama returned a non-finite embedding")
            if expected_dimensions is None:
                expected_dimensions = len(embedding)
            elif len(embedding) != expected_dimensions:
                raise EmbeddingServiceError("Ollama returned inconsistent dimensions")
            embeddings.append(embedding)
        return embeddings
