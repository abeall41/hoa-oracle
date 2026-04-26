import json
import pytest
from app.services.faithfulness import (
    UNVERIFIED_DISCLAIMER,
    check_citation_grounding,
    extract_citations,
)


class TestExtractCitations:
    def test_section_reference(self):
        assert extract_citations("Per Section 12, a quorum is required.") == ["Section 12"]

    def test_decimal_section(self):
        assert extract_citations("Section 2.405 prohibits noise.") == ["Section 2.405"]

    def test_article_reference(self):
        assert "Article VIII" in extract_citations("See Article VIII for details.")

    def test_article_and_section_together(self):
        citations = extract_citations("Article VIII, Section 3 of the bylaws.")
        assert "Article VIII" in citations
        assert "Section 3" in citations

    def test_no_citations(self):
        assert extract_citations("No rules were violated here.") == []

    def test_deduplicates_repeated_reference(self):
        text = "Section 12 says X. Section 12 also says Y."
        assert extract_citations(text) == ["Section 12"]

    def test_case_insensitive_extraction(self):
        citations = extract_citations("Per section 12 and SECTION 13.")
        assert len(citations) == 2

    def test_roman_numeral_article(self):
        assert "Article IV" in extract_citations("As stated in Article IV.")

    def test_does_not_match_bare_numbers(self):
        assert extract_citations("There are 12 units in the building.") == []


class TestCheckCitationGrounding:
    def _facts(self, *chunk_texts: str) -> str:
        return json.dumps({
            "results": [{"chunk_text": t} for t in chunk_texts],
            "query": "test",
            "community_id": 3,
            "tiers_searched": ["community"],
        })

    def test_grounded_citation_passes(self):
        facts = self._facts("Section 12. Quorum. A majority of directors constitutes a quorum.")
        ungrounded, is_suspect = check_citation_grounding(
            "According to Section 12, a majority vote is required.", facts
        )
        assert ungrounded == []
        assert not is_suspect

    def test_ungrounded_single_citation_below_threshold(self):
        facts = self._facts("Dogs must be leashed at all times.")
        ungrounded, is_suspect = check_citation_grounding(
            "Section 2.405 restricts noise.", facts
        )
        assert "Section 2.405" in ungrounded
        assert not is_suspect  # only 1 ungrounded, threshold is 2

    def test_two_ungrounded_triggers_suspect(self):
        facts = self._facts("Pets are permitted with restrictions.")
        _, is_suspect = check_citation_grounding(
            "Section 12 and Section 99 both apply to this situation.", facts
        )
        assert is_suspect

    def test_mixed_grounded_and_ungrounded(self):
        facts = self._facts("Section 4. Restrictions. No commercial vehicles.")
        ungrounded, is_suspect = check_citation_grounding(
            "Section 4 restricts vehicles. Section 99 and Section 100 also apply.", facts
        )
        assert "Section 4" not in ungrounded
        assert "Section 99" in ungrounded
        assert "Section 100" in ungrounded
        assert is_suspect

    def test_case_insensitive_corpus_check(self):
        facts = self._facts("section 12 covers quorum requirements.")
        ungrounded, _ = check_citation_grounding(
            "Per Section 12, a quorum is required.", facts
        )
        assert ungrounded == []

    def test_empty_response_has_no_citations(self):
        facts = self._facts("Some content here.")
        ungrounded, is_suspect = check_citation_grounding("Here is a general answer.", facts)
        assert ungrounded == []
        assert not is_suspect

    def test_multiple_chunks_searched(self):
        facts = self._facts(
            "Section 4. Parking rules apply.",
            "Section 7. Pets must be leashed.",
        )
        ungrounded, is_suspect = check_citation_grounding(
            "Section 4 and Section 7 both apply here.", facts
        )
        assert ungrounded == []
        assert not is_suspect

    def test_malformed_facts_json_falls_back_gracefully(self):
        ungrounded, is_suspect = check_citation_grounding(
            "Section 99 applies here.", "not valid json"
        )
        # Falls back to raw string search — "section 99" not in "not valid json"
        assert "Section 99" in ungrounded

    def test_disclaimer_text_is_non_empty(self):
        assert len(UNVERIFIED_DISCLAIMER) > 20
