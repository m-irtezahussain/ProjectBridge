import struct
import zlib
from pathlib import Path

import pytest

from app.config import Settings
from app.core.services.document_validation import (
    DocumentValidationError,
    DocumentValidationService,
    sanitize_filename,
)


def png_bytes(width: int = 1, height: int = 1) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + (zlib.crc32(kind + payload) & 0xFFFFFFFF).to_bytes(4, "big")
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    pixels = zlib.compress(b"\x00" + b"\x00\x00\x00\xff" * width * height)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", pixels)
        + chunk(b"IEND", b"")
    )


def test_filename_and_declaration_validation() -> None:
    service = DocumentValidationService(Settings())

    assert sanitize_filename("../../client report.pdf") == "client report.pdf"
    assert (
        service.validate_declaration(
            "../client report.pdf", "application/pdf", 120, 1000
        )
        == "client report.pdf"
    )

    with pytest.raises(DocumentValidationError, match="extension"):
        service.validate_declaration("shell.php", "image/jpeg", 120, 1000)
    with pytest.raises(DocumentValidationError, match="between"):
        service.validate_declaration("report.pdf", "application/pdf", 1001, 1000)


def test_magic_bytes_and_png_limits(tmp_path: Path) -> None:
    service = DocumentValidationService(Settings())
    valid = tmp_path / "valid.png"
    valid.write_bytes(png_bytes())

    result = service.validate_file(valid, "image/png")

    assert (result.mime_type, result.width, result.height) == ("image/png", 1, 1)
    with pytest.raises(DocumentValidationError, match="declared MIME"):
        service.validate_file(valid, "image/jpeg")

    oversized = tmp_path / "oversized.png"
    oversized.write_bytes(png_bytes(20_001, 1))
    with pytest.raises(DocumentValidationError, match="dimensions"):
        service.validate_file(oversized, "image/png")

    malformed = tmp_path / "malformed.png"
    malformed.write_bytes(b"\x89PNG\r\n\x1a\n" + b"not-a-real-image")
    with pytest.raises(DocumentValidationError, match="PNG"):
        service.validate_file(malformed, "image/png")


def test_pdf_page_limit_and_structure(tmp_path: Path) -> None:
    service = DocumentValidationService(Settings(document_max_pages=2))
    valid = tmp_path / "valid.pdf"
    valid.write_bytes(b"%PDF-1.7\n1 0 obj<</Type /Page>>endobj\n%%EOF")

    assert service.validate_file(valid, "application/pdf").page_count == 1

    too_many = tmp_path / "too-many.pdf"
    too_many.write_bytes(
        b"%PDF-1.7\n<</Type /Page>><</Type /Page>><</Type /Page>>\n%%EOF"
    )
    with pytest.raises(DocumentValidationError, match="between 1 and 2"):
        service.validate_file(too_many, "application/pdf")

    missing_end = tmp_path / "missing-end.pdf"
    missing_end.write_bytes(b"%PDF-1.7\n<</Type /Page>>")
    with pytest.raises(DocumentValidationError, match="end marker"):
        service.validate_file(missing_end, "application/pdf")


def test_png_decompression_bomb_is_rejected(tmp_path: Path) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            len(payload).to_bytes(4, "big")
            + kind
            + payload
            + (zlib.crc32(kind + payload) & 0xFFFFFFFF).to_bytes(4, "big")
        )

    service = DocumentValidationService(
        Settings(document_max_decompressed_bytes=1024 * 1024)
    )
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    bomb = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"0" * (1024 * 1024 + 1)))
        + chunk(b"IEND", b"")
    )
    path = tmp_path / "bomb.png"
    path.write_bytes(bomb)

    with pytest.raises(DocumentValidationError, match="Decompressed content"):
        service.validate_file(path, "image/png")
