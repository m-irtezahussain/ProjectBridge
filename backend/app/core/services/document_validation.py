import re
import struct
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

ALLOWED_MIME_EXTENSIONS = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
}
PDF_PAGE_PATTERN = re.compile(rb"/Type\s*/Page(?!s)\b")
PDF_PAGE_COUNT_PATTERN = re.compile(rb"/Count\s+(\d+)\b")
PDF_STREAM_PATTERN = re.compile(
    rb"<<(.*?)>>\s*stream\r?\n(.*?)\r?\nendstream", re.DOTALL
)


class DocumentValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ValidatedDocument:
    mime_type: str
    page_count: int | None = None
    width: int | None = None
    height: int | None = None


def sanitize_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFKC", filename).replace("\\", "/")
    leaf = normalized.rsplit("/", maxsplit=1)[-1]
    safe = "".join(
        character
        for character in leaf
        if character.isprintable()
        and character not in {'"', "'", "<", ">", ":", "|", "?", "*"}
    )
    safe = re.sub(r"\s+", " ", safe).strip(" .")[:200]
    if not safe or safe in {".", ".."}:
        raise DocumentValidationError("invalid_filename", "Filename is not valid")
    return safe


class DocumentValidationService:
    def __init__(self, settings: Settings) -> None:
        self._max_pages = settings.document_max_pages
        self._max_pixels = settings.document_max_image_pixels
        self._max_dimension = settings.document_max_image_dimension
        self._max_decompressed = settings.document_max_decompressed_bytes

    def validate_declaration(
        self, filename: str, declared_mime_type: str, size_bytes: int, max_bytes: int
    ) -> str:
        safe_name = sanitize_filename(filename)
        normalized_mime = declared_mime_type.strip().lower()
        extensions = ALLOWED_MIME_EXTENSIONS.get(normalized_mime)
        if extensions is None:
            raise DocumentValidationError(
                "unsupported_type", "Only PDF, PNG, and JPEG documents are supported"
            )
        if Path(safe_name).suffix.lower() not in extensions:
            raise DocumentValidationError(
                "extension_mismatch", "Filename extension does not match the MIME type"
            )
        if size_bytes < 1 or size_bytes > max_bytes:
            raise DocumentValidationError(
                "invalid_size", f"Document must be between 1 and {max_bytes} bytes"
            )
        return safe_name

    def validate_file(self, path: Path, declared_mime_type: str) -> ValidatedDocument:
        with path.open("rb") as file:
            head = file.read(32)
        detected = self._detect_mime(head)
        if detected is None or detected != declared_mime_type:
            raise DocumentValidationError(
                "mime_mismatch", "File content does not match the declared MIME type"
            )
        if detected == "application/pdf":
            return self._validate_pdf(path)
        if detected == "image/png":
            width, height = self._validate_png(path)
        else:
            width, height = self._jpeg_dimensions(path)
        self._validate_dimensions(width, height)
        return ValidatedDocument(
            mime_type=detected,
            width=width,
            height=height,
        )

    @staticmethod
    def _detect_mime(head: bytes) -> str | None:
        if head.startswith(b"%PDF-"):
            return "application/pdf"
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if head.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        return None

    def _validate_pdf(self, path: Path) -> ValidatedDocument:
        data = path.read_bytes()
        if b"%%EOF" not in data[-1024:]:
            raise DocumentValidationError("invalid_pdf", "PDF end marker is missing")
        if b"/Encrypt" in data:
            raise DocumentValidationError(
                "encrypted_pdf", "Encrypted PDF documents are not supported"
            )
        direct_page_count = len(PDF_PAGE_PATTERN.findall(data))
        declared_counts = [
            int(value) for value in PDF_PAGE_COUNT_PATTERN.findall(data)
        ]
        page_count = max([direct_page_count, *declared_counts], default=0)
        if page_count < 1 or page_count > self._max_pages:
            raise DocumentValidationError(
                "page_limit",
                f"PDF must contain between 1 and {self._max_pages} pages",
            )
        decompressed_total = 0
        for match in PDF_STREAM_PATTERN.finditer(data):
            dictionary, stream = match.groups()
            if b"FlateDecode" not in dictionary:
                continue
            decompressed_total += self._bounded_decompressed_size(stream)
            if decompressed_total > self._max_decompressed:
                raise DocumentValidationError(
                    "decompression_limit", "PDF decompressed content exceeds the limit"
                )
        return ValidatedDocument(mime_type="application/pdf", page_count=page_count)

    def _bounded_decompressed_size(self, compressed: bytes) -> int:
        decompressor = zlib.decompressobj()
        total = 0
        try:
            for start in range(0, len(compressed), 64 * 1024):
                remaining = self._max_decompressed - total + 1
                output = decompressor.decompress(
                    compressed[start : start + 64 * 1024], remaining
                )
                total += len(output)
                if total > self._max_decompressed:
                    break
            if total <= self._max_decompressed:
                total += len(
                    decompressor.flush(self._max_decompressed - total + 1)
                )
        except zlib.error as error:
            raise DocumentValidationError(
                "invalid_pdf", "PDF contains an invalid compressed stream"
            ) from error
        if total > self._max_decompressed:
            raise DocumentValidationError(
                "decompression_limit", "Decompressed content exceeds the limit"
            )
        return total

    def _validate_png(self, path: Path) -> tuple[int, int]:
        data = path.read_bytes()
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise DocumentValidationError("invalid_image", "PNG header is invalid")
        offset = 8
        width = height = 0
        compressed = bytearray()
        saw_ihdr = saw_iend = False
        while offset + 12 <= len(data):
            length = int.from_bytes(data[offset : offset + 4], "big")
            chunk_end = offset + 12 + length
            if length > len(data) or chunk_end > len(data):
                raise DocumentValidationError("invalid_image", "PNG chunk is invalid")
            chunk_type = data[offset + 4 : offset + 8]
            chunk_data = data[offset + 8 : offset + 8 + length]
            expected_crc = int.from_bytes(data[offset + 8 + length : chunk_end], "big")
            actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            if expected_crc != actual_crc:
                raise DocumentValidationError("invalid_image", "PNG checksum is invalid")
            if chunk_type == b"IHDR":
                if saw_ihdr or length != 13 or offset != 8:
                    raise DocumentValidationError("invalid_image", "PNG header is invalid")
                width, height = struct.unpack(">II", chunk_data[:8])
                saw_ihdr = True
            elif chunk_type == b"IDAT":
                compressed.extend(chunk_data)
            elif chunk_type == b"IEND":
                if length != 0 or chunk_end != len(data):
                    raise DocumentValidationError("invalid_image", "PNG end chunk is invalid")
                saw_iend = True
                break
            offset = chunk_end
        if not saw_ihdr or not compressed or not saw_iend:
            raise DocumentValidationError("invalid_image", "PNG structure is incomplete")
        self._bounded_decompressed_size(bytes(compressed))
        return width, height

    @staticmethod
    def _jpeg_dimensions(path: Path) -> tuple[int, int]:
        with path.open("rb") as complete_file:
            complete_file.seek(-2, 2)
            if complete_file.read(2) != b"\xff\xd9":
                raise DocumentValidationError("invalid_image", "JPEG end marker is missing")
        with path.open("rb") as file:
            if file.read(2) != b"\xff\xd8":
                raise DocumentValidationError("invalid_image", "JPEG header is invalid")
            while True:
                byte = file.read(1)
                while byte == b"\xff":
                    byte = file.read(1)
                if not byte:
                    break
                marker = byte[0]
                if marker in {0xD8, 0xD9}:
                    continue
                length_bytes = file.read(2)
                if len(length_bytes) != 2:
                    break
                segment_length = int.from_bytes(length_bytes, "big")
                if segment_length < 2:
                    break
                if marker in {
                    0xC0,
                    0xC1,
                    0xC2,
                    0xC3,
                    0xC5,
                    0xC6,
                    0xC7,
                    0xC9,
                    0xCA,
                    0xCB,
                    0xCD,
                    0xCE,
                    0xCF,
                }:
                    payload = file.read(5)
                    if len(payload) != 5:
                        break
                    return (
                        int.from_bytes(payload[3:5], "big"),
                        int.from_bytes(payload[1:3], "big"),
                    )
                file.seek(segment_length - 2, 1)
        raise DocumentValidationError("invalid_image", "JPEG dimensions are missing")

    def _validate_dimensions(self, width: int, height: int) -> None:
        if (
            width < 1
            or height < 1
            or width > self._max_dimension
            or height > self._max_dimension
            or width * height > self._max_pixels
            or width * height * 4 > self._max_decompressed
        ):
            raise DocumentValidationError(
                "image_dimension_limit", "Image dimensions exceed the configured limit"
            )
