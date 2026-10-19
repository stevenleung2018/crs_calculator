"""Domain models for a Comprehensive Ranking System (CRS) profile.

All models are immutable dataclasses so a profile can be hashed, compared,
serialized and replayed exactly (reproducibility). Language ability is always
stored as a Canadian Language Benchmark (CLB) / Niveaux de compétence
linguistique canadiens (NCLC) level; raw test scores are converted in
:mod:`crs_calculator.language`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

#: Lowest CLB level we store. Anything below CLB 4 is recorded as 3 and earns
#: no points anywhere in the CRS.
MIN_CLB = 3
#: Highest CLB level that matters for the CRS ("CLB 10 or more").
MAX_CLB = 10

ABILITIES: tuple[str, ...] = ("speaking", "listening", "reading", "writing")


class Language(str, Enum):
    """Canada's two official languages."""

    ENGLISH = "english"
    FRENCH = "french"


class LanguageTest(str, Enum):
    """Language tests accepted by IRCC for Express Entry.

    ``CLB_DIRECT`` is not a test: it lets a user type CLB/NCLC levels directly
    (useful for simulation and for people who already know their levels).
    """

    IELTS_GENERAL = "ielts_general"
    CELPIP_GENERAL = "celpip_general"
    PTE_CORE = "pte_core"
    TEF_CANADA = "tef_canada"
    TCF_CANADA = "tcf_canada"
    CLB_DIRECT = "clb_direct"

    @property
    def language(self) -> Language | None:
        """Official language assessed by the test (``None`` for direct entry)."""
        if self in (LanguageTest.IELTS_GENERAL, LanguageTest.CELPIP_GENERAL, LanguageTest.PTE_CORE):
            return Language.ENGLISH
        if self in (LanguageTest.TEF_CANADA, LanguageTest.TCF_CANADA):
            return Language.FRENCH
        return None


class EducationLevel(str, Enum):
    """Highest level of education (Canadian credential or ECA), in CRS order."""

    LESS_THAN_SECONDARY = "less_than_secondary"
    SECONDARY = "secondary"
    ONE_YEAR = "one_year"
    TWO_YEAR = "two_year"
    BACHELORS = "bachelors"
    TWO_OR_MORE = "two_or_more"
    MASTERS = "masters"
    PHD = "phd"

    @property
    def label(self) -> str:
        return EDUCATION_LABELS[self]

    @property
    def is_post_secondary(self) -> bool:
        return self not in (EducationLevel.LESS_THAN_SECONDARY, EducationLevel.SECONDARY)


EDUCATION_LABELS: dict[EducationLevel, str] = {
    EducationLevel.LESS_THAN_SECONDARY: "Less than secondary school (high school)",
    EducationLevel.SECONDARY: "Secondary diploma (high school graduation)",
    EducationLevel.ONE_YEAR: "One-year post-secondary program",
    EducationLevel.TWO_YEAR: "Two-year post-secondary program",
    EducationLevel.BACHELORS: "Bachelor's degree or 3+ year program",
    EducationLevel.TWO_OR_MORE: "Two or more credentials (one of 3+ years)",
    EducationLevel.MASTERS: "Master's or entry-to-practice professional degree",
    EducationLevel.PHD: "Doctoral degree (PhD)",
}


class CanadianEducation(str, Enum):
    """Post-secondary credential earned in Canada (additional points)."""

    NONE = "none"
    ONE_OR_TWO_YEARS = "one_or_two_years"
    THREE_YEARS_OR_MORE = "three_years_or_more"

    @property
    def label(self) -> str:
        return {
            CanadianEducation.NONE: "None / secondary or less",
            CanadianEducation.ONE_OR_TWO_YEARS: "One- or two-year credential",
            CanadianEducation.THREE_YEARS_OR_MORE: "3+ year credential, or Master's / professional / PhD",
        }[self]


class HighWageLevel(str, Enum):
    """High-wage occupation level (Labour Market Integration factor, Nov 2026).

    The level is a property of the NOC occupation, expressed as a multiple of
    the average median wage of the Canadian workforce.
    """

    NONE = "none"
    X1_3 = "x1.3"
    X1_5 = "x1.5"
    X2_0 = "x2.0"

    @property
    def label(self) -> str:
        return {
            HighWageLevel.NONE: "Not a high-wage occupation / none",
            HighWageLevel.X1_3: "At least 1.3x the median wage",
            HighWageLevel.X1_5: "At least 1.5x the median wage",
            HighWageLevel.X2_0: "At least 2x the median wage",
        }[self]


@dataclass(frozen=True)
class LanguageResult:
    """CLB/NCLC level for each of the four abilities on one test."""

    test: LanguageTest
    speaking: int
    listening: int
    reading: int
    writing: int
    #: Required when ``test`` is ``CLB_DIRECT``; otherwise inferred from the test.
    language_override: Language | None = None
    #: Original test scores (speaking, listening, reading, writing), kept so a
    #: saved scenario can restore exactly what was entered. Not used for scoring.
    raw_scores: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.raw_scores is not None and len(self.raw_scores) != len(ABILITIES):
            raise ValueError("raw_scores must contain four values (speaking, listening, reading, writing)")
        for ability in ABILITIES:
            level = getattr(self, ability)
            if not isinstance(level, int) or not MIN_CLB <= level <= 12:
                raise ValueError(f"{ability} CLB must be an integer between {MIN_CLB} and 12, got {level!r}")
        if self.test is LanguageTest.CLB_DIRECT and self.language_override is None:
            raise ValueError("language_override is required when entering CLB levels directly")
        if self.test.language is not None and self.language_override not in (None, self.test.language):
            raise ValueError(f"{self.test.value} assesses {self.test.language.value}, not {self.language_override}")

    @property
    def language(self) -> Language:
        lang = self.test.language or self.language_override
        assert lang is not None  # guaranteed by __post_init__
        return lang

    @property
    def levels(self) -> dict[str, int]:
        """Ability -> CLB, capped at :data:`MAX_CLB` (CLB 10+ scores the same)."""
        return {a: min(getattr(self, a), MAX_CLB) for a in ABILITIES}

    @property
    def min_level(self) -> int:
        return min(self.levels.values())

    def all_at_least(self, level: int) -> bool:
        return self.min_level >= level

    @classmethod
    def uniform(cls, language: Language, level: int) -> LanguageResult:
        """Same CLB/NCLC on all four abilities (handy for simulations)."""
        return cls(LanguageTest.CLB_DIRECT, level, level, level, level, language_override=language)


@dataclass(frozen=True)
class SpouseProfile:
    """Factors for an accompanying spouse or common-law partner."""

    education: EducationLevel = EducationLevel.SECONDARY
    canadian_work_years: int = 0
    language: LanguageResult | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.canadian_work_years <= 5:
            raise ValueError("spouse canadian_work_years must be between 0 and 5 (5 means 5 or more)")


@dataclass(frozen=True)
class Profile:
    """Everything the CRS needs about a principal applicant.

    Work-experience years are whole years, with the top category meaning
    "or more" (5 for Canadian, 3 for foreign), matching the official calculator.
    """

    age: int
    education: EducationLevel
    first_language: LanguageResult
    second_language: LanguageResult | None = None
    canadian_work_years: int = 0
    foreign_work_years: int = 0
    certificate_of_qualification: bool = False
    canadian_education: CanadianEducation = CanadianEducation.NONE
    provincial_nomination: bool = False
    sibling_in_canada: bool = False
    #: Spouse/partner who accompanies the applicant and is not a Canadian
    #: citizen or permanent resident. ``None`` means "score as single".
    spouse: SpouseProfile | None = None
    #: Nov 2026 rules: high-wage level with >= 12 months Canadian experience.
    high_wage_experience: HighWageLevel = HighWageLevel.NONE
    #: Nov 2026 rules: high-wage level of a qualifying job offer.
    job_offer: HighWageLevel = HighWageLevel.NONE
    notes: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not 0 <= self.age <= 120:
            raise ValueError("age must be between 0 and 120")
        if not 0 <= self.canadian_work_years <= 5:
            raise ValueError("canadian_work_years must be between 0 and 5 (5 means 5 or more)")
        if not 0 <= self.foreign_work_years <= 3:
            raise ValueError("foreign_work_years must be between 0 and 3 (3 means 3 or more)")
        if self.second_language is not None and self.second_language.language is self.first_language.language:
            raise ValueError("second official language must differ from the first")

    @property
    def has_spouse(self) -> bool:
        return self.spouse is not None

    def language_for(self, language: Language) -> LanguageResult | None:
        """Return the test result for ``language`` regardless of first/second order."""
        for result in (self.first_language, self.second_language):
            if result is not None and result.language is language:
                return result
        return None

    def evolve(self, **changes: Any) -> Profile:
        """Return a copy with ``changes`` applied (used by simulations)."""
        return replace(self, **changes)
