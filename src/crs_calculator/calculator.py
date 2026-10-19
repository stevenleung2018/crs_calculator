"""Pure, deterministic CRS calculation with a line-by-line audit trail.

``calculate(profile, rules)`` returns a :class:`CRSResult` whose ``items``
explain every point awarded (input used, points, maximum, rule applied and the
official source). Section caps are recorded as explicit negative "cap" items,
so the items always sum exactly to the reported total.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from . import rules as R
from .models import (
    ABILITIES,
    CanadianEducation,
    EducationLevel,
    HighWageLevel,
    Language,
    LanguageResult,
    Profile,
    SpouseProfile,
)


class Section(str, Enum):
    CORE = "A. Core / human capital"
    SPOUSE = "B. Spouse or common-law partner"
    TRANSFERABILITY = "C. Skill transferability"
    ADDITIONAL = "D. Additional points"
    LABOUR_MARKET = "E. Labour Market Integration"


@dataclass(frozen=True)
class LineItem:
    """One explainable contribution to the score."""

    section: Section
    factor: str
    input: str
    points: int
    max_points: int | None
    rule: str
    source: str = "criteria"

    @property
    def source_url(self) -> str:
        return R.SOURCES[self.source]


@dataclass(frozen=True)
class CRSResult:
    rules: R.RuleSet
    items: tuple[LineItem, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total(self) -> int:
        return sum(item.points for item in self.items)

    def section_total(self, section: Section) -> int:
        return sum(item.points for item in self.items if item.section is section)

    @property
    def section_totals(self) -> dict[Section, int]:
        sections = [s for s in Section if any(i.section is s for i in self.items)]
        return {s: self.section_total(s) for s in sections}


def _col(with_spouse: bool) -> int:
    """Index into ``(with spouse, without spouse)`` tuples."""
    return 0 if with_spouse else 1


def _clb_text(result: LanguageResult) -> str:
    return ", ".join(f"{a[0].upper()}{result.levels[a]}" for a in ABILITIES)


def _cap(section: Section, subtotal: int, cap: int, label: str) -> list[LineItem]:
    if subtotal <= cap:
        return []
    return [
        LineItem(
            section,
            f"Cap: {label}",
            f"subtotal {subtotal}",
            cap - subtotal,
            None,
            f"{label} is capped at {cap} points.",
        )
    ]


# --- A. Core ----------------------------------------------------------------


def _core(profile: Profile, with_spouse: bool, include_canadian_work: bool) -> list[LineItem]:
    c = _col(with_spouse)
    column = "with spouse/partner" if with_spouse else "without spouse/partner"
    items: list[LineItem] = []

    age_points = R.AGE_POINTS.get(profile.age, (0, 0))[c]
    items.append(
        LineItem(
            Section.CORE,
            "Age",
            f"{profile.age} years",
            age_points,
            (100, 110)[c],
            f"Age table, {column}. 20-29 earns the maximum; 17 or younger and 45 or older earn 0.",
        )
    )
    items.append(
        LineItem(
            Section.CORE,
            "Level of education",
            profile.education.label,
            R.EDUCATION_POINTS[profile.education][c],
            (140, 150)[c],
            f"Education table, {column}.",
        )
    )

    first = profile.first_language
    for ability in ABILITIES:
        level = first.levels[ability]
        items.append(
            LineItem(
                Section.CORE,
                f"First official language ({first.language.value.capitalize()}) - {ability}",
                f"CLB {level}" if level >= 4 else "below CLB 4",
                R.FIRST_LANGUAGE_POINTS[level][c],
                (32, 34)[c],
                f"Per-ability table, {column}: CLB 4-5 = 6, CLB 10+ = maximum.",
            )
        )

    second = profile.second_language
    if second is not None:
        second_items = [
            LineItem(
                Section.CORE,
                f"Second official language ({second.language.value.capitalize()}) - {ability}",
                f"CLB {second.levels[ability]}",
                R.SECOND_LANGUAGE_POINTS[second.levels[ability]],
                6,
                "CLB 5-6 = 1, CLB 7-8 = 3, CLB 9+ = 6 per ability.",
            )
            for ability in ABILITIES
        ]
        subtotal = sum(i.points for i in second_items)
        items += second_items + _cap(Section.CORE, subtotal, R.SECOND_LANGUAGE_CAP[c], "Second official language")

    if include_canadian_work:
        years = profile.canadian_work_years
        items.append(
            LineItem(
                Section.CORE,
                "Canadian work experience",
                _years(years, 5),
                R.CANADIAN_WORK_POINTS[years][c],
                (70, 80)[c],
                f"Canadian work experience table, {column}.",
            )
        )
    return items


def _years(years: int, top: int) -> str:
    if years == 0:
        return "none or less than 1 year"
    suffix = " or more" if years >= top else ""
    return f"{years} year{'s' if years != 1 else ''}{suffix}"


# --- B. Spouse --------------------------------------------------------------


def _spouse(spouse: SpouseProfile) -> list[LineItem]:
    items = [
        LineItem(
            Section.SPOUSE,
            "Spouse education",
            spouse.education.label,
            R.SPOUSE_EDUCATION_POINTS[spouse.education],
            10,
            "Spouse education table.",
        )
    ]
    if spouse.language is None:
        items.append(
            LineItem(
                Section.SPOUSE,
                "Spouse first official language",
                "no test",
                0,
                20,
                "No language test entered for the spouse.",
            )
        )
    else:
        for ability in ABILITIES:
            level = spouse.language.levels[ability]
            items.append(
                LineItem(
                    Section.SPOUSE,
                    f"Spouse language - {ability}",
                    f"CLB {level}",
                    R.SPOUSE_LANGUAGE_POINTS[level],
                    5,
                    "CLB 5-6 = 1, CLB 7-8 = 3, CLB 9+ = 5 per ability.",
                )
            )
    items.append(
        LineItem(
            Section.SPOUSE,
            "Spouse Canadian work experience",
            _years(spouse.canadian_work_years, 5),
            R.SPOUSE_CANADIAN_WORK_POINTS[spouse.canadian_work_years],
            10,
            "Spouse Canadian work table.",
        )
    )
    return items


# --- C. Skill transferability ----------------------------------------------


def _language_tier(result: LanguageResult, low: int, high: int) -> int | None:
    """0 = lower tier (all >= low, some < high), 1 = higher tier (all >= high)."""
    if result.all_at_least(high):
        return 1
    if result.all_at_least(low):
        return 0
    return None


def _canadian_work_tier(years: int) -> int | None:
    return None if years < 1 else (0 if years == 1 else 1)


def _education_points(level: EducationLevel) -> tuple[int, int] | None:
    if level in R.EDUCATION_ONE_CREDENTIAL:
        return R.TRANSFER_EDUCATION_ONE_CREDENTIAL
    if level in R.EDUCATION_TWO_OR_ADVANCED:
        return R.TRANSFER_EDUCATION_TWO_OR_ADVANCED
    return None


def _foreign_points(years: int) -> tuple[int, int] | None:
    if years >= 3:
        return R.TRANSFER_FOREIGN_3_PLUS_YEARS
    if years >= 1:
        return R.TRANSFER_FOREIGN_1_TO_2_YEARS
    return None


def _transferability(profile: Profile) -> list[LineItem]:
    s = Section.TRANSFERABILITY
    lang_tier = _language_tier(profile.first_language, 7, 9)
    cwe_tier = _canadian_work_tier(profile.canadian_work_years)
    lang_text = f"first language {_clb_text(profile.first_language)}"
    cwe_text = f"Canadian work {_years(profile.canadian_work_years, 5)}"
    tier_rule = "lower tier (CLB 7+ all, one under 9 / 1 year Canadian) vs higher tier (CLB 9+ all / 2+ years Canadian)"

    def combo(name: str, table: tuple[int, int] | None, tier: int | None, detail: str) -> LineItem:
        points = table[tier] if table is not None and tier is not None else 0
        return LineItem(s, name, detail, points, table[1] if table else 50, f"Points depend on the {tier_rule}.")

    edu_table = _education_points(profile.education)
    edu_items = [
        combo("Education + official language", edu_table, lang_tier, f"{profile.education.label}; {lang_text}"),
        combo("Education + Canadian work experience", edu_table, cwe_tier, f"{profile.education.label}; {cwe_text}"),
    ]
    fwe_table = _foreign_points(profile.foreign_work_years)
    fwe_text = f"foreign work {_years(profile.foreign_work_years, 3)}"
    fwe_items = [
        combo("Foreign work + official language", fwe_table, lang_tier, f"{fwe_text}; {lang_text}"),
        combo("Foreign work + Canadian work experience", fwe_table, cwe_tier, f"{fwe_text}; {cwe_text}"),
    ]

    coq_points = 0
    if profile.certificate_of_qualification:
        coq_tier = _language_tier(profile.first_language, 5, 7)
        coq_points = R.TRANSFER_CERTIFICATE[coq_tier] if coq_tier is not None else 0
    coq_item = LineItem(
        s,
        "Certificate of qualification + official language",
        f"{'has' if profile.certificate_of_qualification else 'no'} certificate; {lang_text}",
        coq_points,
        50,
        "CLB 5+ all (one under 7) = 25; CLB 7+ all = 50.",
    )

    items: list[LineItem] = []
    edu_sub = sum(i.points for i in edu_items)
    fwe_sub = sum(i.points for i in fwe_items)
    items += edu_items + _cap(s, edu_sub, R.TRANSFER_SUBGROUP_CAP, "Education combinations")
    items += fwe_items + _cap(s, fwe_sub, R.TRANSFER_SUBGROUP_CAP, "Foreign work combinations")
    items.append(coq_item)
    subtotal = min(edu_sub, 50) + min(fwe_sub, 50) + coq_points
    items += _cap(s, subtotal, R.TRANSFER_TOTAL_CAP, "Skill transferability")
    return items


# --- D. Additional ----------------------------------------------------------


def _french_bonus(profile: Profile) -> LineItem:
    french = profile.language_for(Language.FRENCH)
    english = profile.language_for(Language.ENGLISH)
    rule = (
        "NCLC 7+ on all four French abilities: 50 if English is CLB 5+ on all four, "
        "otherwise 25 (English CLB 4 or lower, or no English test)."
    )
    if french is None:
        return LineItem(Section.ADDITIONAL, "French language skills", "no French test", 0, 50, rule)
    detail = f"French {_clb_text(french)}; English {_clb_text(english) if english else 'no test'}"
    if not french.all_at_least(7):
        points = 0
    elif english is not None and english.all_at_least(5):
        points = R.FRENCH_AND_ENGLISH_POINTS
    else:
        points = R.FRENCH_ONLY_POINTS
    return LineItem(Section.ADDITIONAL, "French language skills", detail, points, 50, rule)


def _additional(profile: Profile, warnings: list[str]) -> list[LineItem]:
    s = Section.ADDITIONAL
    canadian_edu = profile.canadian_education
    if canadian_edu is not CanadianEducation.NONE and not profile.education.is_post_secondary:
        warnings.append("Canadian post-secondary education ignored: highest education is secondary or less.")
        canadian_edu = CanadianEducation.NONE
    items = [
        LineItem(
            s,
            "Provincial or territorial nomination",
            "yes" if profile.provincial_nomination else "no",
            R.PROVINCIAL_NOMINATION_POINTS if profile.provincial_nomination else 0,
            600,
            "Nomination = 600.",
        ),
        LineItem(
            s,
            "Sibling in Canada (citizen or PR)",
            "yes" if profile.sibling_in_canada else "no",
            R.SIBLING_POINTS if profile.sibling_in_canada else 0,
            15,
            "Applicant or accompanying spouse has a brother/sister 18+ in Canada who is a citizen or PR.",
        ),
        _french_bonus(profile),
        LineItem(
            s,
            "Post-secondary education in Canada",
            canadian_edu.label,
            R.CANADIAN_EDUCATION_POINTS[canadian_edu],
            30,
            "1-2 year credential = 15; 3+ years = 30.",
        ),
    ]
    subtotal = sum(i.points for i in items)
    return items + _cap(s, subtotal, R.ADDITIONAL_CAP, "Additional points")


# --- E. Labour Market Integration (Nov 2026) --------------------------------


def _labour_market(profile: Profile, with_spouse: bool, warnings: list[str]) -> list[LineItem]:
    s = Section.LABOUR_MARKET
    c = _col(with_spouse)
    years = profile.canadian_work_years
    work_length = R.CANADIAN_WORK_POINTS[years][c]

    high_wage = profile.high_wage_experience
    if high_wage is not HighWageLevel.NONE and years < 1:
        warnings.append("High-wage experience points need at least 1 year (1,560 hours) of Canadian work experience.")
        high_wage = HighWageLevel.NONE
    high_wage_points = R.HIGH_WAGE_EXPERIENCE_POINTS[high_wage]
    experience_option = work_length + high_wage_points
    offer_option = R.JOB_OFFER_POINTS[profile.job_offer]

    use_offer = offer_option > experience_option
    chosen = "job offer option" if use_offer else "Canadian work experience option"
    compare = (
        f"Compared options: work experience {experience_option} vs job offer {offer_option}; "
        f"the {chosen} is used (points are not combined)."
    )
    items = [
        LineItem(
            s,
            "Canadian work experience - work length",
            _years(years, 5),
            0 if use_offer else work_length,
            (70, 80)[c],
            compare,
            "changes_2026",
        ),
        LineItem(
            s,
            "Canadian work experience - high-wage occupation",
            high_wage.label,
            0 if use_offer else high_wage_points,
            70,
            "At least 12 months in high-wage occupations: 2x = 70, 1.5x = 40, 1.3x = 20.",
            "changes_2026",
        ),
        LineItem(
            s,
            "Qualifying job offer (no LMIA needed)",
            profile.job_offer.label,
            offer_option if use_offer else 0,
            100,
            "High-wage job offer: 2x = 100, 1.5x = 70, 1.3x = 50; not a high-wage occupation = 0.",
            "changes_2026",
        ),
    ]
    subtotal = max(experience_option, offer_option)
    return items + _cap(s, subtotal, R.LABOUR_MARKET_INTEGRATION_CAP[c], "Labour Market Integration factor")


# --- Public API -------------------------------------------------------------


def calculate(profile: Profile, rules: R.RuleSet = R.RULES_2025_03) -> CRSResult:
    """Compute the CRS score for ``profile`` under ``rules``."""
    warnings: list[str] = []
    with_spouse = profile.has_spouse
    items = _core(profile, with_spouse, include_canadian_work=not rules.labour_market_integration)
    if profile.spouse is not None:
        items += _spouse(profile.spouse)
    items += _transferability(profile)
    items += _additional(profile, warnings)
    if rules.labour_market_integration:
        items += _labour_market(profile, with_spouse, warnings)
    elif profile.job_offer is not HighWageLevel.NONE or profile.high_wage_experience is not HighWageLevel.NONE:
        warnings.append(
            "Job offers and high-wage occupations earn no CRS points under the rules in force since "
            "March 25, 2025. Switch to the November 3, 2026 rules to see their effect."
        )
    if profile.age < 18:
        warnings.append("Applicants aged 17 or younger receive 0 age points.")
    return CRSResult(rules=rules, items=tuple(items), warnings=tuple(warnings))
