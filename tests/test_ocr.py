import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPDFTextExtraction:
    async def test_text_layer_pdf_skips_ocr(self):
        """PDFs with a text layer should not trigger Tesseract."""
        # TODO: implement with a small synthetic PDF fixture
        pytest.skip("requires PDF fixture")

    async def test_scanned_pdf_triggers_tesseract(self):
        """PDFs with no text layer should go through Tesseract."""
        pytest.skip("requires scanned PDF fixture")


class TestOCRConfidenceThreshold:
    async def test_low_confidence_triggers_ollama_cleanup(self, mock_llm_client):
        """Tesseract confidence below threshold should call complete_ocr_cleanup."""
        pytest.skip("requires low-confidence OCR fixture")

    async def test_high_confidence_skips_ollama(self, mock_llm_client):
        """Tesseract confidence above threshold should not call complete_ocr_cleanup."""
        pytest.skip("requires high-confidence OCR fixture")


class TestOllamaUnavailable:
    async def test_ollama_unavailable_continues_with_raw_text(self, mocker):
        """If Ollama is unreachable during OCR cleanup, ingestion must continue."""
        from app.services.ocr import _ocr_with_tesseract
        from app.services.llm import OllamaUnavailableError

        mocker.patch(
            "app.services.ocr.LLMClient.complete_ocr_cleanup",
            side_effect=OllamaUnavailableError("Ollama unreachable"),
        )
        pytest.skip("requires Tesseract fixture")
