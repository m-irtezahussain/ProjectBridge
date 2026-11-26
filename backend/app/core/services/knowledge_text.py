import re
import unicodedata

WHITESPACE = re.compile(r"[\t ]+")
EXCESS_NEWLINES = re.compile(r"\n{3,}")


def normalize_knowledge_text(value: str) -> str:
    """Normalize untrusted searchable text without interpreting its contents."""
    normalized = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    normalized = "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or unicodedata.category(character) != "Cc"
    )
    lines = [WHITESPACE.sub(" ", line).strip() for line in normalized.split("\n")]
    return EXCESS_NEWLINES.sub("\n\n", "\n".join(lines)).strip()


def chunk_knowledge_text(
    value: str,
    *,
    max_characters: int,
    overlap_characters: int,
) -> list[str]:
    """Create deterministic overlapping chunks from normalized, untrusted text."""
    if overlap_characters >= max_characters:
        raise ValueError("Chunk overlap must be smaller than chunk size")
    text = normalize_knowledge_text(value)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        hard_end = min(len(text), start + max_characters)
        end = hard_end
        if hard_end < len(text):
            minimum_break = start + max_characters // 2
            paragraph_break = text.rfind("\n\n", minimum_break, hard_end)
            word_break = text.rfind(" ", minimum_break, hard_end)
            end = max(paragraph_break, word_break)
            if end <= start:
                end = hard_end
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        next_start = max(0, end - overlap_characters)
        start = next_start if next_start > start else end
    return chunks
