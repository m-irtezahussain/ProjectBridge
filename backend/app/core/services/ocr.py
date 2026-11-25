from __future__ import annotations

import asyncio
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Protocol


class OCRError(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRResult:
    text: str
    page_count: int
    average_confidence: float | None
    engine: str
    engine_version: str
    model: str
    language: str


class OCRProvider(Protocol):
    async def extract(self, path: Path) -> OCRResult: ...


class PaddleOCRProvider:
    """Worker-only PaddleOCR adapter; model output is always untrusted text."""

    def __init__(self, model: str, language: str) -> None:
        self._model_name = model
        self._language = language
        self._predictor: Any | None = None

    def _load(self) -> Any:
        if self._predictor is None:
            try:
                from paddleocr import PaddleOCR  # type: ignore[import-not-found]
            except ImportError as error:
                raise OCRError("PaddleOCR worker dependencies are not installed") from error
            self._predictor = PaddleOCR(
                ocr_version="PP-OCRv6",
                text_detection_model_name=f"{self._model_name}_det",
                text_recognition_model_name=f"{self._model_name}_rec",
                lang=self._language,
                use_doc_orientation_classify=True,
                use_doc_unwarping=False,
                use_textline_orientation=True,
            )
        return self._predictor

    async def extract(self, path: Path) -> OCRResult:
        return await asyncio.to_thread(self._extract_sync, path)

    def _extract_sync(self, path: Path) -> OCRResult:
        predictor = self._load()
        try:
            outputs = list(predictor.predict(str(path)))
        except Exception as error:
            raise OCRError("OCR inference failed") from error
        texts: list[str] = []
        scores: list[float] = []
        for output in outputs:
            payload = getattr(output, "json", output)
            if callable(payload):
                payload = payload()
            if not isinstance(payload, dict):
                continue
            result = payload.get("res", payload)
            if not isinstance(result, dict):
                continue
            page_texts = result.get("rec_texts", [])
            page_scores = result.get("rec_scores", [])
            texts.extend(str(value) for value in page_texts if str(value).strip())
            scores.extend(float(value) for value in page_scores)
        if not texts:
            raise OCRError("OCR produced no text")
        return OCRResult(
            text="\n".join(texts),
            page_count=max(1, len(outputs)),
            average_confidence=sum(scores) / len(scores) if scores else None,
            engine="paddleocr",
            engine_version=self._package_version(),
            model=self._model_name,
            language=self._language,
        )

    @staticmethod
    def _package_version() -> str:
        try:
            return version("paddleocr")
        except PackageNotFoundError:
            return "unknown"
