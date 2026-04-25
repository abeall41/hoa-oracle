import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_llm_client(mocker):
    """Mock LLMClient so tests never make live API calls."""
    mock = AsyncMock()
    mock.complete = AsyncMock(return_value="Mocked LLM response")
    mock.complete_ocr_cleanup = AsyncMock(return_value="Cleaned OCR text")
    mocker.patch("app.services.llm.LLMClient", return_value=mock)
    return mock


@pytest.fixture
def mock_db_session(mocker):
    """Mock AsyncSession for unit tests that don't need a live DB."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    mocker.patch("app.database.AsyncSessionLocal", return_value=session)
    return session
