from __future__ import annotations

import pytest

from conftest import clb
from crs_calculator import (
    RULES_2025_03,
    RULES_2026_11,
    CanadianEducation,
    EducationLevel,
    HighWageLevel,
    Language,
    LanguageResult,
    LanguageTest,
    Profile,
    Section,
    SpouseProfile,
    calculate,
)


def test_single_masters_hand_checked(single_masters: Profile) -> None:
    result = calculate(single_masters)
    # Core: age 110 + education 135 + language 4*31 + Canadian work 40 = 409
    assert result.section_total(Section.CORE) == 409
    # Both transferability subgroups hit their 50-point caps.
    assert result.section_total(Section.TRANSFERABILITY) == 100
    assert result.total == 509


def test_items_always_sum_to_total(single_masters: Profile) -> None:
    result = calculate(single_masters.evolve(provincial_nomination=True, sibling_in_canada=True))
    assert sum(i.points for i in result.items) == result.total
    assert sum(result.section_totals.values()) == result.total


def test_with_accompanying_spouse(single_masters: Profile) -> None:
    spouse = SpouseProfile(education=EducationLevel.BACHELORS, language=clb(7))
    result = calculate(single_masters.evolve(spouse=spouse))
    # Core with spouse: 100 + 126 + 4*29 + 35 = 377
    assert result.section_total(Section.CORE) == 377
    # Spouse: education 8 + language 4*3 + Canadian work 0 = 20
    assert result.section_total(Section.SPOUSE) == 20
    assert result.total == 377 + 20 + 100


@pytest.mark.parametrize(
    ("age", "single", "married"),
    [(17, 0, 0), (18, 99, 90), (25, 110, 100), (30, 105, 95), (40, 50, 45), (44, 6, 5), (45, 0, 0)],
)
def test_age_points(age: int, single: int, married: int, single_masters: Profile) -> None:
    def age_points(p: Profile) -> int:
        return next(i.points for i in calculate(p).items if i.factor == "Age")

    assert age_points(single_masters.evolve(age=age)) == single
    assert age_points(single_masters.evolve(age=age, spouse=SpouseProfile())) == married


def test_second_language_cap_with_spouse(single_masters: Profile) -> None:
    profile = single_masters.evolve(second_language=clb(9, Language.FRENCH), spouse=SpouseProfile())
    items = [i for i in calculate(profile).items if i.section is Section.CORE]
    second = [i for i in items if i.factor.startswith("Second official language")]
    cap = [i for i in items if i.factor.startswith("Cap: Second")]
    assert sum(i.points for i in second) == 24
    assert cap and cap[0].points == -2  # capped at 22 with a spouse


@pytest.mark.parametrize(
    ("french", "english", "expected"),
    [
        (7, 5, 50),  # NCLC 7 + CLB 5 on all English abilities
        (7, 4, 25),  # English CLB 4 or lower
        (6, 9, 0),  # French below NCLC 7
        (10, None, 25),  # no English test
    ],
)
def test_french_bonus(french: int, english: int | None, expected: int) -> None:
    if english is None:
        profile = Profile(age=30, education=EducationLevel.BACHELORS, first_language=clb(french, Language.FRENCH))
    else:
        profile = Profile(
            age=30,
            education=EducationLevel.BACHELORS,
            first_language=clb(english),
            second_language=clb(french, Language.FRENCH),
        )
    bonus = next(i for i in calculate(profile).items if i.factor == "French language skills")
    assert bonus.points == expected


def test_french_bonus_mixed_english_scores_25() -> None:
    english = LanguageResult(LanguageTest.CLB_DIRECT, 9, 9, 9, 4, language_override=Language.ENGLISH)
    profile = Profile(
        age=30, education=EducationLevel.BACHELORS, first_language=english, second_language=clb(8, Language.FRENCH)
    )
    bonus = next(i for i in calculate(profile).items if i.factor == "French language skills")
    assert bonus.points == 25


def test_certificate_of_qualification_tiers() -> None:
    base = Profile(age=30, education=EducationLevel.SECONDARY, first_language=clb(6), certificate_of_qualification=True)
    coq = "Certificate of qualification + official language"
    assert next(i.points for i in calculate(base).items if i.factor == coq) == 25
    assert next(i.points for i in calculate(base.evolve(first_language=clb(7))).items if i.factor == coq) == 50
    assert next(i.points for i in calculate(base.evolve(first_language=clb(4))).items if i.factor == coq) == 0


def test_transferability_total_cap() -> None:
    profile = Profile(
        age=30,
        education=EducationLevel.PHD,
        first_language=clb(10),
        foreign_work_years=3,
        certificate_of_qualification=True,
    )
    assert calculate(profile).section_total(Section.TRANSFERABILITY) == 100


def test_additional_points_capped_at_600(single_masters: Profile) -> None:
    profile = single_masters.evolve(
        provincial_nomination=True,
        sibling_in_canada=True,
        canadian_education=CanadianEducation.THREE_YEARS_OR_MORE,
    )
    assert calculate(profile).section_total(Section.ADDITIONAL) == 600


def test_canadian_education_requires_post_secondary() -> None:
    profile = Profile(
        age=30,
        education=EducationLevel.SECONDARY,
        first_language=clb(9),
        canadian_education=CanadianEducation.ONE_OR_TWO_YEARS,
    )
    result = calculate(profile)
    assert result.section_total(Section.ADDITIONAL) == 0
    assert result.warnings


def test_job_offer_scores_zero_under_2025_rules(single_masters: Profile) -> None:
    profile = single_masters.evolve(job_offer=HighWageLevel.X2_0)
    result = calculate(profile, RULES_2025_03)
    assert result.total == calculate(single_masters, RULES_2025_03).total
    assert any("no CRS points" in w for w in result.warnings)


class TestLabourMarketIntegration:
    def test_same_total_without_high_wage_or_offer(self, single_masters: Profile) -> None:
        assert calculate(single_masters, RULES_2026_11).total == calculate(single_masters, RULES_2025_03).total

    def test_work_experience_option_max_150(self, single_masters: Profile) -> None:
        profile = single_masters.evolve(canadian_work_years=5, high_wage_experience=HighWageLevel.X2_0)
        assert calculate(profile, RULES_2026_11).section_total(Section.LABOUR_MARKET) == 150

    def test_work_experience_option_max_140_with_spouse(self, single_masters: Profile) -> None:
        profile = single_masters.evolve(
            canadian_work_years=5, high_wage_experience=HighWageLevel.X2_0, spouse=SpouseProfile()
        )
        assert calculate(profile, RULES_2026_11).section_total(Section.LABOUR_MARKET) == 140

    def test_job_offer_wins_when_higher(self, single_masters: Profile) -> None:
        # Work option: 40 (1 year) + 20 (1.3x) = 60; job offer at 2x = 100.
        profile = single_masters.evolve(high_wage_experience=HighWageLevel.X1_3, job_offer=HighWageLevel.X2_0)
        assert calculate(profile, RULES_2026_11).section_total(Section.LABOUR_MARKET) == 100

    def test_options_are_not_combined(self, single_masters: Profile) -> None:
        # Work option: 80 (5 years) vs job offer 70 -> 80, not 150.
        profile = single_masters.evolve(canadian_work_years=5, job_offer=HighWageLevel.X1_5)
        assert calculate(profile, RULES_2026_11).section_total(Section.LABOUR_MARKET) == 80

    def test_high_wage_needs_one_year(self, single_masters: Profile) -> None:
        profile = single_masters.evolve(canadian_work_years=0, high_wage_experience=HighWageLevel.X2_0)
        result = calculate(profile, RULES_2026_11)
        assert result.section_total(Section.LABOUR_MARKET) == 0
        assert result.warnings

    def test_transferability_still_uses_work_length(self, single_masters: Profile) -> None:
        profile = single_masters.evolve(job_offer=HighWageLevel.X2_0)
        assert calculate(profile, RULES_2026_11).section_total(Section.TRANSFERABILITY) == 100
