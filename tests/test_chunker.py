from app.services.chunker import chunk_text, CHUNK_SIZE_TOKENS, _detect_section_ref


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_returns_single_chunk():
    chunks = chunk_text("This is a short paragraph about parking rules.")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0


def test_chunk_indices_are_sequential():
    long_text = "\n\n".join([f"Paragraph {i}. " + "Word " * 80 for i in range(20)])
    chunks = chunk_text(long_text)
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_chunks_respect_size_target():
    long_text = "\n\n".join(["Word " * 200 for _ in range(10)])
    chunks = chunk_text(long_text)
    for chunk in chunks:
        token_estimate = len(chunk.content) // 4
        # Allow some overflow at boundaries
        assert token_estimate < CHUNK_SIZE_TOKENS * 2


def test_section_ref_detected_for_article_headings():
    text = "Article IV, Section 2\n\nThe board shall consist of five members elected annually."
    chunks = chunk_text(text)
    assert chunks[0].section_ref is not None
    assert "Article" in chunks[0].section_ref


def test_detect_section_ref_returns_none_for_plain_text():
    assert _detect_section_ref("No heading here, just plain text.") is None


def test_detect_section_ref_finds_section_heading():
    ref = _detect_section_ref("Section 4.2 Parking Rules\nNo more than two vehicles...")
    assert ref is not None
    assert "Section" in ref


def test_chunk_text_is_data_type_agnostic():
    """chunk_text must handle any text content, not just legal documents."""
    email_text = (
        "From: board@wickford.org\nTo: homeowners@wickford.org\n\n"
        "Dear Residents,\n\n"
        "This is a reminder about the upcoming annual meeting.\n\n"
        "Please RSVP by Friday."
    )
    chunks = chunk_text(email_text)
    assert len(chunks) >= 1
    assert all(c.content for c in chunks)
