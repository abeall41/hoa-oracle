import logging
from pathlib import Path

from app.config import settings
from app.services.llm import LLMClient, OllamaUnavailableError

logger = logging.getLogger(__name__)


class OCRResult:
    def __init__(self, text: str, confidence: float, ocr_applied: bool) -> None:
        self.text = text
        self.confidence = confidence
        self.ocr_applied = ocr_applied


async def extract_text_from_pdf(file_bytes: bytes) -> OCRResult:
    """
    Extract text from a PDF.
    Tries the text layer first (PyMuPDF); falls back to Tesseract OCR if no text found.
    If Tesseract confidence < settings.ocr_confidence_threshold, runs Ollama cleanup.
    If Ollama is unavailable, logs a warning and returns raw Tesseract output.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text_layers = [page.get_text() for page in doc]
    combined = "\n".join(text_layers).strip()

    if combined:
        return OCRResult(text=combined, confidence=1.0, ocr_applied=False)

    # No text layer — fall back to Tesseract
    return await _ocr_with_tesseract(file_bytes)


async def extract_text_from_docx(file_bytes: bytes) -> OCRResult:
    """Extract text from a DOCX file using python-docx."""
    import io
    from docx import Document

    doc = Document(io.BytesIO(file_bytes))
    text = "\n".join(para.text for para in doc.paragraphs).strip()
    return OCRResult(text=text, confidence=1.0, ocr_applied=False)


async def _ocr_with_tesseract(file_bytes: bytes) -> OCRResult:
    """Run Tesseract OCR on PDF bytes. Runs Ollama cleanup if confidence is low."""
    import io
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    all_text = []
    confidences = []

    for page in doc:
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        page_text = " ".join(
            w for w in data["text"] if w.strip()
        )
        page_confs = [c for c in data["conf"] if c != -1]
        if page_confs:
            confidences.extend(page_confs)
        all_text.append(page_text)

    raw_text = "\n".join(all_text)
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
