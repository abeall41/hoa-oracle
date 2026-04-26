import logging
import re
from pathlib import Path

from app.config import settings
from app.services.llm import LLMClient, OllamaUnavailableError

# Matches rotated court-stamp text that Montgomery County land records systems
# print on the left margin of every page. Tesseract picks these up as running
# text; strip them before storing or chunking.
_COURT_STAMP_RE = re.compile(
    r"\S+\.\s*Date available \d{2}/\d{2}/\d{4}\..*?PAGE:\s*\d+\s*",
    re.IGNORECASE | re.DOTALL,
)


def _strip_court_stamps(text: str) -> str:
    return _COURT_STAMP_RE.sub("", text).strip()

logger = logging.getLogger(__name__)


class OCRResult:
    def __init__(self, text: str, confidence: float, ocr_applied: bool, page_count: int = 0) -> None:
        self.text = text
        self.confidence = confidence
        self.ocr_applied = ocr_applied
        self.page_count = page_count


_MIN_CHARS_PER_PAGE = 200  # below this average => treat as scanned (marginal stamps only)


async def extract_text_from_pdf(file_bytes: bytes) -> OCRResult:
    """
    Extract text from a PDF.
    Tries the text layer first (PyMuPDF); falls back to Tesseract OCR when:
      - no text layer is present, OR
      - average chars per page is below _MIN_CHARS_PER_PAGE (indicates only marginal
        stamps or headers are embedded, while actual content is a scanned image).
    If Tesseract confidence < settings.ocr_confidence_threshold, runs Ollama cleanup.
    If Ollama is unavailable, logs a warning and returns raw Tesseract output.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    num_pages = doc.page_count or 1
    text_layers = [page.get_text() for page in doc]
    combined = "\n".join(text_layers).strip()

    avg_chars = len(combined) / num_pages
    if combined and avg_chars >= _MIN_CHARS_PER_PAGE:
        return OCRResult(text=_strip_court_stamps(combined), confidence=1.0, ocr_applied=False, page_count=num_pages)

    if combined:
        logger.info(
            "PDF text layer present but sparse (%.0f avg chars/page < %d threshold) — "
            "falling back to Tesseract OCR",
            avg_chars,
            _MIN_CHARS_PER_PAGE,
        )

    # No meaningful text layer — fall back to Tesseract
    result = await _ocr_with_tesseract(file_bytes)
    result.page_count = num_pages
    return result


async def extract_text_from_docx(file_bytes: bytes) -> OCRResult:
    """Extract text from a DOCX file using python-docx."""
    import io
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    text = "\n".join(para.text for para in doc.paragraphs).strip()
    return OCRResult(text=text, confidence=1.0, ocr_applied=False)


async def _ocr_with_tesseract(file_bytes: bytes) -> OCRResult:
    """
    Run Tesseract OCR on PDF bytes.
    Uses image_to_string (psm 1) to preserve paragraph structure and section headings.
    Uses image_to_data separately to compute confidence.
    Strips court-stamp margin text before storing.
    Runs Ollama cleanup if confidence is below threshold.
    """
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    all_text = []
    confidences = []

    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # image_to_string with auto page segmentation preserves newlines,
        # paragraph breaks, and heading structure that image_to_data flattens.
        page_text = pytesseract.image_to_string(img, config="--psm 1")
        page_text = _strip_court_stamps(page_text)
        all_text.append(page_text)

        # image_to_data for per-word confidence scores only
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        page_confs = [c for c in data["conf"] if isinstance(c, (int, float)) and c != -1]
        confidences.extend(page_confs)

    raw_text = "\n\n".join(all_text)  # double newline between pages
    mean_confidence = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0

    if mean_confidence < settings.ocr_confidence_threshold:
        logger.info(
            "Tesseract confidence %.2f below threshold %.2f — attempting Ollama cleanup",
            mean_confidence,
            settings.ocr_confidence_threshold,
        )
        try:
            llm = LLMClient()
            raw_text = await llm.complete_ocr_cleanup(raw_text)
        except OllamaUnavailableError:
            logger.warning("Ollama unavailable for OCR cleanup — storing raw Tesseract output")

    return OCRResult(text=raw_text, confidence=mean_confidence, ocr_applied=True)
