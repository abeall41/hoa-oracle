"""
Citation grounding checks for LLM synthesis output.

Gate 3 of the accuracy pipeline: after synthesis, extract all Section/Article
references from the response and verify each appears in the retrieved source
material. Ungrounded citations are a reliable signal of hallucination.
"""
import json as _json
import logging
import re

logger = logging.getLogger(__name__)

# Matches "Section 12", "Section 2.405", "Article VIII", "Article 5"
# Intentionally does not match bare numbers to avoid false positives.
_CITATION_RE = re.compile(
    r"\b(?:Article\s+[IVXLCDM\d]+|Section\s+\d+(?:\.\d+)*)",
    re.IGNORECASE,
)

# Number of ungrounded citations required before flagging as suspect.
# 1 may be a partial match issue; 2+ is a reliable hallucination signal.
_UNGROUNDED_THRESHOLD = 2

# Appended to response when retry still contains ungrounded citations.
UNVERIFIED_DISCLAIMER = (
    "\n\n*Note: One or more section references in this response could not be "
    "verified against the retrieved source documents. Please confirm specific "
    "citations directly in your governing documents before acting on this "
    "information.*"
)


def extract_citations(text: str) -> list[str]:
    """Extract all Section/Article reference strings from LLM response text."""
    return list(dict.fromkeys(m.group(0) for m in _CITATION_RE.finditer(text)))


def check_citation_grounding(
    response_text: str,
    compliance_facts_json: str,
) -> tuple[list[str], bool]:
    """
    Verify that citations in response_text are grounded in compliance_facts_json.

    Builds a corpus from all retrieved chunk texts and checks each extracted
    Section/Article reference. A citation is considered grounded if its full
    string appears (case-insensitive) in the corpus.

    Returns:
        ungrounded: citation strings not found in any retrieved chunk
        is_suspect: True when ungrounded count >= _UNGROUNDED_THRESHOLD
    """
    citations = extract_citations(response_text)
    if not citations:
        return [], False

    try:
        facts = _json.loads(compliance_facts_json)
        corpus = " ".join(
            chunk.get("chunk_text", "") for chunk in facts.get("results", [])
        ).lower()
    except Exception:
        corpus = compliance_facts_json.lower()

    ungrounded = [c for c in citations if c.lower() not in corpus]
    is_suspect = len(ungrounded) >= _UNGROUNDED_THRESHOLD

    if ungrounded:
        logger.warning(
            "Citation grounding: %d/%d ungrounded %s (suspect=%s)",
            len(ungrounded), len(citations), ungrounded, is_suspect,
        )
    else:
        logger.debug("Citation grounding: all %d citations verified", len(citations))

    return ungrounded, is_suspect
