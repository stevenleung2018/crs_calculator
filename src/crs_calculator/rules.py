"""Versioned CRS points tables.

Every number here is transcribed from official IRCC pages (see ``SOURCES``).
Tables are keyed by ``with_spouse`` (``True`` = applicant has an accompanying
spouse/partner who is not a Canadian citizen or permanent resident).

Two rule sets are provided:

* ``2025-03-25`` - rules in force since arranged-employment (job offer) points
  were removed on March 25, 2025.
* ``2026-11-03`` - adds the Labour Market Integration factor announced on
  October 16, 2026 (high-wage Canadian work experience or job offer).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType

from .models import CanadianEducation, EducationLevel, HighWageLevel

SOURCES: Mapping[str, str] = MappingProxyType(
    {
        "calculator": "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/check-score.html",
        "criteria": "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/check-score/crs-criteria.html",
        "changes_2026": "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/changes.html",
        "backgrounder_2026": "https://www.canada.ca/en/immigration-refugees-citizenship/news/2026/10/changes-to-express-entry-for-high-wage-occupations.html",
        "language_testing": "https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents/language-requirements/language-testing.html",
    }
)


def _freeze(table: dict) -> Mapping:
    return MappingProxyType(table)


# --- A. Core / human capital ------------------------------------------------

#: age -> (with spouse, without spouse); ages <= 17 and >= 45 score 0.
AGE_POINTS: Mapping[int, tuple[int, int]] = _freeze(
    {
        18: (90, 99),
        19: (95, 105),
        **{age: (100, 110) for age in range(20, 30)},
        30: (95, 105),
        31: (90, 99),
        32: (85, 94),
        33: (80, 88),
        34: (75, 83),
        35: (70, 77),
        36: (65, 72),
        37: (60, 66),
        38: (55, 61),
        39: (50, 55),
        40: (45, 50),
        41: (35, 39),
        42: (25, 28),
        43: (15, 17),
        44: (5, 6),
    }
)

EDUCATION_POINTS: Mapping[EducationLevel, tuple[int, int]] = _freeze(
    {
        EducationLevel.LESS_THAN_SECONDARY: (0, 0),
        EducationLevel.SECONDARY: (28, 30),
        EducationLevel.ONE_YEAR: (84, 90),
        EducationLevel.TWO_YEAR: (91, 98),
        EducationLevel.BACHELORS: (112, 120),
        EducationLevel.TWO_OR_MORE: (119, 128),
        EducationLevel.MASTERS: (126, 135),
        EducationLevel.PHD: (140, 150),
    }
)

#: First official language, per ability: CLB -> (with spouse, without spouse).
FIRST_LANGUAGE_POINTS: Mapping[int, tuple[int, int]] = _freeze(
    {3: (0, 0), 4: (6, 6), 5: (6, 6), 6: (8, 9), 7: (16, 17), 8: (22, 23), 9: (29, 31), 10: (32, 34)}
)

#: Second official language, per ability (same for both columns).
SECOND_LANGUAGE_POINTS: Mapping[int, int] = _freeze({3: 0, 4: 0, 5: 1, 6: 1, 7: 3, 8: 3, 9: 6, 10: 6})
#: Section cap for the second official language: (with spouse, without spouse).
SECOND_LANGUAGE_CAP: tuple[int, int] = (22, 24)

#: Canadian work experience (years, 5 = 5+) -> (with spouse, without spouse).
CANADIAN_WORK_POINTS: Mapping[int, tuple[int, int]] = _freeze(
    {0: (0, 0), 1: (35, 40), 2: (46, 53), 3: (56, 64), 4: (63, 72), 5: (70, 80)}
)

# --- B. Spouse / common-law partner ------------------------------------------

SPOUSE_EDUCATION_POINTS: Mapping[EducationLevel, int] = _freeze(
    {
        EducationLevel.LESS_THAN_SECONDARY: 0,
        EducationLevel.SECONDARY: 2,
        EducationLevel.ONE_YEAR: 6,
        EducationLevel.TWO_YEAR: 7,
        EducationLevel.BACHELORS: 8,
        EducationLevel.TWO_OR_MORE: 9,
        EducationLevel.MASTERS: 10,
        EducationLevel.PHD: 10,
    }
)
#: Spouse language, per ability: CLB -> points (max 5 per ability, 20 total).
SPOUSE_LANGUAGE_POINTS: Mapping[int, int] = _freeze({3: 0, 4: 0, 5: 1, 6: 1, 7: 3, 8: 3, 9: 5, 10: 5})
SPOUSE_CANADIAN_WORK_POINTS: Mapping[int, int] = _freeze({0: 0, 1: 5, 2: 7, 3: 8, 4: 9, 5: 10})

# --- C. Skill transferability -----------------------------------------------

#: Points for a combination at (lower tier, higher tier) of the paired factor.
#: e.g. education "one credential" with CLB 7-8 -> 13, with CLB 9+ -> 25.
TRANSFER_EDUCATION_ONE_CREDENTIAL: tuple[int, int] = (13, 25)
TRANSFER_EDUCATION_TWO_OR_ADVANCED: tuple[int, int] = (25, 50)
TRANSFER_FOREIGN_1_TO_2_YEARS: tuple[int, int] = (13, 25)
TRANSFER_FOREIGN_3_PLUS_YEARS: tuple[int, int] = (25, 50)
TRANSFER_CERTIFICATE: tuple[int, int] = (25, 50)
TRANSFER_SUBGROUP_CAP = 50
TRANSFER_TOTAL_CAP = 100

#: Education levels that count as "one post-secondary credential of 1+ year".
EDUCATION_ONE_CREDENTIAL = frozenset({EducationLevel.ONE_YEAR, EducationLevel.TWO_YEAR, EducationLevel.BACHELORS})
#: "Two or more credentials (one 3+ years)", Master's/professional, or PhD.
EDUCATION_TWO_OR_ADVANCED = frozenset({EducationLevel.TWO_OR_MORE, EducationLevel.MASTERS, EducationLevel.PHD})

# --- D. Additional points ----------------------------------------------------

PROVINCIAL_NOMINATION_POINTS = 600
SIBLING_POINTS = 15
FRENCH_ONLY_POINTS = 25  # NCLC 7+ all four, English CLB 4 or lower / no test
FRENCH_AND_ENGLISH_POINTS = 50  # NCLC 7+ all four, English CLB 5+ all four
CANADIAN_EDUCATION_POINTS: Mapping[CanadianEducation, int] = _freeze(
    {CanadianEducation.NONE: 0, CanadianEducation.ONE_OR_TWO_YEARS: 15, CanadianEducation.THREE_YEARS_OR_MORE: 30}
)
ADDITIONAL_CAP = 600

# --- Labour Market Integration factor (from 2026-11-03) ----------------------

HIGH_WAGE_EXPERIENCE_POINTS: Mapping[HighWageLevel, int] = _freeze(
    {HighWageLevel.NONE: 0, HighWageLevel.X1_3: 20, HighWageLevel.X1_5: 40, HighWageLevel.X2_0: 70}
)
JOB_OFFER_POINTS: Mapping[HighWageLevel, int] = _freeze(
    {HighWageLevel.NONE: 0, HighWageLevel.X1_3: 50, HighWageLevel.X1_5: 70, HighWageLevel.X2_0: 100}
)
#: Factor cap: (with spouse, without spouse).
LABOUR_MARKET_INTEGRATION_CAP: tuple[int, int] = (140, 150)


@dataclass(frozen=True)
class RuleSet:
    """Identifies which version of the CRS rules to apply."""

    id: str
    name: str
    effective_from: date
    #: If True, Canadian work experience is scored inside the Labour Market
    #: Integration factor (with high-wage and job offer options).
    labour_market_integration: bool
    description: str


RULES_2025_03 = RuleSet(
    id="2025-03-25",
    name="Current rules (since March 25, 2025)",
    effective_from=date(2025, 3, 25),
    labour_market_integration=False,
    description=(
        "No CRS points for job offers (arranged employment points were removed on "
        "March 25, 2025). Canadian work experience is scored in the core factors."
    ),
)

RULES_2026_11 = RuleSet(
    id="2026-11-03",
    name="Labour Market Integration factor (from November 3, 2026)",
    effective_from=date(2026, 11, 3),
    labour_market_integration=True,
    description=(
        "Canadian work experience (work-length points plus high-wage occupation points) "
        "OR a qualifying high-wage job offer, whichever is higher; max 150 (140 with spouse)."
    ),
)

RULE_SETS: Mapping[str, RuleSet] = MappingProxyType({r.id: r for r in (RULES_2025_03, RULES_2026_11)})


def rules_in_force(on: date) -> RuleSet:
    """Return the most recent rule set whose effective date is on or before ``on``."""
    eligible = [r for r in RULE_SETS.values() if r.effective_from <= on]
    if not eligible:
        raise ValueError(f"no rule set modelled before {on.isoformat()}")
    return max(eligible, key=lambda r: r.effective_from)


def get_rules(rule_id: str) -> RuleSet:
    try:
        return RULE_SETS[rule_id]
    except KeyError as exc:
        raise ValueError(f"unknown rule set {rule_id!r}; choose from {sorted(RULE_SETS)}") from exc
