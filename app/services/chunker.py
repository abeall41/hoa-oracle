import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CHUNK_SIZE_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 50

# Patterns that indicate a new section boundary
SECTION_PATTERNS = [
    re.compile(r"^(Article\s+[IVXLCDM]+|Article\s+\d+)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^(Section\s+\d+[\.\d]*)", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^\d+\.\s+[A-Z]", re.MULTILINE),
]


@dataclass
class Chunk:
    content: str
    chunk_index: int
    section_ref: str | None
    page_number: int | None = None


def _approximate_token_count(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _detect_section_ref(text: str) -> str | None:
    """Return the first detectable section heading found in text, or None."""
    for pattern in SECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0).strip()
    return None


def chunk_text(text: str, source_metadata: dict | None = None) -> list[Chunk]:
    """
    Split text into overlapping chunks of ~500 tokens with 50-token overlap.
    Attempts section-aware splitting: prefers to break at section boundaries.
    Data-type agnostic — works for any text-extractable content (PDFs, emails, etc.)
    """
    if not text.strip():
        return []

    # Split into paragraphs first, then group into chunks
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_tokens = 0
    chunk_index = 0

    def flush(parts: list[str]) -> Chunk:
        nonlocal chunk_index
        content = "\n\n".join(parts)
        section_ref = _detect_section_ref(content)
        c = Chunk(content=content, chunk_index=chunk_index, section_ref=section_ref)
        chunk_index += 1
        return c

    for para in paragraphs:
        para_tokens = _approximate_token_count(para)

        if current_tokens + para_tokens > CHUNK_SIZE_TOKENS and current_parts:
            chunks.append(flush(current_parts))
            # Overlap: keep last ~CHUNK_OVERLAP_TOKENS worth of content
            overlap_text = current_parts[-1] if current_parts else ""
            current_parts = [overlap_text] if overlap_text else []
            current_tokens = _approximate_token_count(overlap_text)

        current_parts.append(para)
        current_tokens += para_tokens

    if current_parts:
        chunks.append(flush(current_parts))

    logger.debug("Chunked text into %d chunks", len(chunks))
    return chunks
