import re
from dataclasses import dataclass

TASK_LINE = re.compile(r"^\s*(?:TODO|TASK|ACTION)\s*[:\-]\s*(.+)$", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedTaskCandidate:
    title: str
    source_excerpt: str
    confidence: float
    source_line_start: int
    source_line_end: int


class SafeTaskCandidateExtractor:
    """Deterministic extraction only; OCR text can never invoke tools or permissions."""

    name = "safe_marker_extractor"
    version = "1.0"

    def extract(self, untrusted_text: str) -> list[ExtractedTaskCandidate]:
        candidates: list[ExtractedTaskCandidate] = []
        seen: set[str] = set()
        for line_number, raw_line in enumerate(untrusted_text.splitlines(), start=1):
            match = TASK_LINE.match(raw_line)
            if match is None:
                continue
            title = " ".join(match.group(1).split())[:200]
            if len(title) < 2 or title.casefold() in seen:
                continue
            seen.add(title.casefold())
            candidates.append(
                ExtractedTaskCandidate(
                    title=title,
                    source_excerpt=raw_line.strip()[:500],
                    confidence=0.8,
                    source_line_start=line_number,
                    source_line_end=line_number,
                )
            )
        return candidates


def chunk_untrusted_text(text: str, max_characters: int = 1500) -> list[str]:
    paragraphs = [value.strip() for value in text.split("\n\n") if value.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if current and len(current) + len(paragraph) + 2 > max_characters:
            chunks.append(current)
            current = ""
        if len(paragraph) > max_characters:
            chunks.extend(
                paragraph[start : start + max_characters]
                for start in range(0, len(paragraph), max_characters)
            )
        else:
            current = f"{current}\n\n{paragraph}" if current else paragraph
    if current:
        chunks.append(current)
    return chunks
