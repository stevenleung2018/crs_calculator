from __future__ import annotations

import pytest

from crs_calculator import EducationLevel, Language, LanguageResult, LanguageTest, Profile


def clb(level: int, language: Language = Language.ENGLISH) -> LanguageResult:
    return LanguageResult.uniform(language, level)


@pytest.fixture
def single_masters() -> Profile:
    """Single, 29, Master's, CLB 9 English, 1 yr Canadian, 3 yrs foreign work."""
    return Profile(
        age=29,
        education=EducationLevel.MASTERS,
        first_language=LanguageResult(LanguageTest.CELPIP_GENERAL, 9, 9, 9, 9),
        canadian_work_years=1,
        foreign_work_years=3,
    )
