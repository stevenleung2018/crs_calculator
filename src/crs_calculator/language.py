"""Convert raw language-test scores to CLB / NCLC levels.

Thresholds come from IRCC's "Documents for Express Entry: Language testing"
page (Federal Skilled Trades tables, which list CLB 4 through 10):
https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents/language-requirements/language-testing.html

Each table maps a CLB level to the *minimum* score needed on each ability.
Scores below the CLB 4 threshold are recorded as CLB 3 ("less than CLB 4").
TEF Canada uses the "Équivalence ancien score" column, as IRCC instructs.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .models import ABILITIES, MAX_CLB, MIN_CLB, Language, LanguageResult, LanguageTest

LANGUAGE_TESTING_URL = (
    "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/"
    "express-entry/documents/language-requirements/language-testing.html"
)

# CLB level -> (speaking, listening, reading, writing) minimum scores.
_Thresholds = Mapping[int, tuple[float, float, float, float]]

_IELTS_GENERAL: _Thresholds = {
    10: (7.5, 8.5, 8.0, 7.5),
    9: (7.0, 8.0, 7.0, 7.0),
    8: (6.5, 7.5, 6.5, 6.5),
    7: (6.0, 6.0, 6.0, 6.0),
    6: (5.5, 5.5, 5.0, 5.5),
    5: (5.0, 5.0, 4.0, 5.0),
    4: (4.0, 4.5, 3.5, 4.0),
}

_PTE_CORE: _Thresholds = {
    10: (89, 89, 88, 90),
    9: (84, 82, 78, 88),
    8: (76, 71, 69, 79),
    7: (68, 60, 60, 69),
    6: (59, 50, 51, 60),
    5: (51, 39, 42, 51),
    4: (42, 28, 33, 41),
}

_TEF_CANADA: _Thresholds = {
    10: (393, 316, 263, 393),
    9: (371, 298, 248, 371),
    8: (349, 280, 233, 349),
    7: (310, 249, 207, 310),
    6: (271, 217, 181, 271),
    5: (226, 181, 151, 226),
    4: (181, 145, 121, 181),
}

_TCF_CANADA: _Thresholds = {
    10: (16, 549, 549, 16),
    9: (14, 523, 524, 14),
    8: (12, 503, 499, 12),
    7: (10, 458, 453, 10),
    6: (7, 398, 406, 7),
    5: (6, 369, 375, 6),
    4: (4, 331, 342, 4),
}

# CELPIP-General levels map 1:1 to CLB (CLB 4-12), so it needs no table.
_CELPIP: _Thresholds = {level: (level, level, level, level) for level in range(MAX_CLB, 3, -1)}


@dataclass(frozen=True)
class ScoreSpec:
    """Valid score range and step for one ability on one test (for UI inputs)."""

    minimum: float
    maximum: float
    step: float


TEST_LABELS: dict[LanguageTest, str] = {
    LanguageTest.CELPIP_GENERAL: "CELPIP-General (English)",
    LanguageTest.IELTS_GENERAL: "IELTS General Training (English)",
    LanguageTest.PTE_CORE: "PTE Core (English)",
    LanguageTest.TEF_CANADA: "TEF Canada (French)",
    LanguageTest.TCF_CANADA: "TCF Canada (French)",
    LanguageTest.CLB_DIRECT: "Enter CLB / NCLC levels directly",
}

THRESHOLDS: dict[LanguageTest, _Thresholds] = {
    LanguageTest.IELTS_GENERAL: _IELTS_GENERAL,
    LanguageTest.CELPIP_GENERAL: _CELPIP,
    LanguageTest.PTE_CORE: _PTE_CORE,
    LanguageTest.TEF_CANADA: _TEF_CANADA,
    LanguageTest.TCF_CANADA: _TCF_CANADA,
}

SCORE_SPECS: dict[LanguageTest, dict[str, ScoreSpec]] = {
    LanguageTest.IELTS_GENERAL: {a: ScoreSpec(0, 9, 0.5) for a in ABILITIES},
    LanguageTest.CELPIP_GENERAL: {a: ScoreSpec(0, 12, 1) for a in ABILITIES},
    LanguageTest.PTE_CORE: {a: ScoreSpec(10, 90, 1) for a in ABILITIES},
    LanguageTest.TEF_CANADA: {
        "speaking": ScoreSpec(0, 450, 1),
        "listening": ScoreSpec(0, 360, 1),
        "reading": ScoreSpec(0, 300, 1),
        "writing": ScoreSpec(0, 450, 1),
    },
    LanguageTest.TCF_CANADA: {
        "speaking": ScoreSpec(0, 20, 1),
        "listening": ScoreSpec(0, 699, 1),
        "reading": ScoreSpec(0, 699, 1),
        "writing": ScoreSpec(0, 20, 1),
    },
    LanguageTest.CLB_DIRECT: {a: ScoreSpec(MIN_CLB, MAX_CLB, 1) for a in ABILITIES},
}


def tests_for(language: Language) -> list[LanguageTest]:
    """Tests that assess ``language`` (excluding direct CLB entry)."""
    return [t for t in THRESHOLDS if t.language is language]


def score_to_clb(test: LanguageTest, ability: str, score: float) -> int:
    """Convert one ability score to a CLB/NCLC level (3 means "below CLB 4")."""
    if ability not in ABILITIES:
        raise ValueError(f"unknown ability {ability!r}; expected one of {ABILITIES}")
    if test is LanguageTest.CLB_DIRECT:
        return max(MIN_CLB, min(int(score), MAX_CLB))
    spec = SCORE_SPECS[test][ability]
    if not spec.minimum <= score <= spec.maximum:
        raise ValueError(
            f"{TEST_LABELS[test]} {ability} score must be in [{spec.minimum}, {spec.maximum}], got {score}"
        )
    index = ABILITIES.index(ability)
    for level in sorted(THRESHOLDS[test], reverse=True):
        if score >= THRESHOLDS[test][level][index]:
            return level
    return MIN_CLB


def result_from_scores(
    test: LanguageTest,
    scores: Mapping[str, float],
    language: Language | None = None,
) -> LanguageResult:
    """Build a :class:`LanguageResult` from raw scores for all four abilities.

    ``language`` is only needed (and only allowed to differ from ``None``) when
    ``test`` is :attr:`LanguageTest.CLB_DIRECT`.
    """
    missing = set(ABILITIES) - set(scores)
    if missing:
        raise ValueError(f"missing scores for {sorted(missing)}")
    levels = {a: score_to_clb(test, a, float(scores[a])) for a in ABILITIES}
    override = language if test is LanguageTest.CLB_DIRECT else None
    raw = tuple(float(scores[a]) for a in ABILITIES)
    return LanguageResult(test=test, language_override=override, raw_scores=raw, **levels)  # type: ignore[arg-type]
