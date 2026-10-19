from __future__ import annotations

import pytest

from crs_calculator import Language, LanguageResult, LanguageTest
from crs_calculator.language import result_from_scores, score_to_clb


@pytest.mark.parametrize(
    ("test", "ability", "score", "expected"),
    [
        (LanguageTest.IELTS_GENERAL, "listening", 8.5, 10),
        (LanguageTest.IELTS_GENERAL, "listening", 7.5, 8),
        (LanguageTest.IELTS_GENERAL, "listening", 7.0, 7),
        (LanguageTest.IELTS_GENERAL, "reading", 3.5, 4),
        (LanguageTest.IELTS_GENERAL, "speaking", 3.5, 3),
        (LanguageTest.CELPIP_GENERAL, "writing", 12, 10),
        (LanguageTest.CELPIP_GENERAL, "writing", 2, 3),
        (LanguageTest.PTE_CORE, "writing", 89, 9),
        (LanguageTest.PTE_CORE, "speaking", 68, 7),
        (LanguageTest.TEF_CANADA, "reading", 207, 7),
        (LanguageTest.TEF_CANADA, "reading", 206, 6),
        (LanguageTest.TCF_CANADA, "speaking", 10, 7),
        (LanguageTest.TCF_CANADA, "listening", 549, 10),
        (LanguageTest.TCF_CANADA, "listening", 330, 3),
    ],
)
def test_score_to_clb(test: LanguageTest, ability: str, score: float, expected: int) -> None:
    assert score_to_clb(test, ability, score) == expected


def test_out_of_range_score_rejected() -> None:
    with pytest.raises(ValueError):
        score_to_clb(LanguageTest.IELTS_GENERAL, "reading", 9.5)


def test_result_from_scores_infers_language() -> None:
    result = result_from_scores(
        LanguageTest.TEF_CANADA, {"speaking": 400, "listening": 300, "reading": 250, "writing": 371}
    )
    assert result.language is Language.FRENCH
    assert result.levels == {"speaking": 10, "listening": 9, "reading": 9, "writing": 9}


def test_direct_entry_requires_language() -> None:
    with pytest.raises(ValueError):
        LanguageResult(LanguageTest.CLB_DIRECT, 7, 7, 7, 7)


def test_test_language_mismatch_rejected() -> None:
    with pytest.raises(ValueError):
        LanguageResult(LanguageTest.IELTS_GENERAL, 7, 7, 7, 7, language_override=Language.FRENCH)
