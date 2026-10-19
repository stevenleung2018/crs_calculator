"""What-if simulations built on top of :func:`calculate`.

Every simulation starts from a baseline :class:`Profile`, changes exactly one
or two factors, and recomputes the full score, so results are directly
comparable and reproducible.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import pandas as pd

from .calculator import CRSResult, Section, calculate
from .models import MAX_CLB, MIN_CLB, EducationLevel, Language, LanguageResult, Profile
from .rules import RULE_SETS, RuleSet

CLB_RANGE: tuple[int, ...] = tuple(range(MIN_CLB, MAX_CLB + 1))


def with_language_level(profile: Profile, language: Language, level: int) -> Profile:
    """Set ``language`` to ``level`` on all four abilities.

    If the profile already has a test in that language it is replaced in
    place (first or second official language). Otherwise the language is added
    as the second official language.
    """
    new = LanguageResult.uniform(language, level)
    if profile.first_language.language is language:
        return profile.evolve(first_language=new)
    return profile.evolve(second_language=new)


def _row(result: CRSResult) -> dict[str, int]:
    row = {"total": result.total}
    for section in Section:
        row[section.value] = result.section_total(section)
    french = next((i for i in result.items if i.factor == "French language skills"), None)
    row["french_bonus"] = french.points if french else 0
    return row


def sweep(
    profile: Profile,
    rules: RuleSet,
    name: str,
    values: Iterable[Any],
    apply: Callable[[Profile, Any], Profile],
) -> pd.DataFrame:
    """Generic one-factor sweep: one row per value, with section subtotals."""
    baseline = calculate(profile, rules).total
    rows = []
    for value in values:
        result = calculate(apply(profile, value), rules)
        rows.append({name: value, **_row(result), "change_vs_baseline": result.total - baseline})
    return pd.DataFrame(rows)


def french_nclc_sweep(profile: Profile, rules: RuleSet, levels: Iterable[int] = CLB_RANGE) -> pd.DataFrame:
    """Score as French NCLC (uniform across abilities) varies.

    NCLC 3 means "below NCLC 4", i.e. effectively no usable French result.
    """
    return sweep(profile, rules, "nclc", levels, lambda p, lvl: with_language_level(p, Language.FRENCH, int(lvl)))


def language_grid(
    profile: Profile,
    rules: RuleSet,
    english_levels: Iterable[int] = CLB_RANGE,
    french_levels: Iterable[int] = CLB_RANGE,
) -> pd.DataFrame:
    """Total score for every (English CLB, French NCLC) combination (long format)."""
    rows = []
    for clb in english_levels:
        p_en = with_language_level(profile, Language.ENGLISH, clb)
        for nclc in french_levels:
            p = with_language_level(p_en, Language.FRENCH, nclc)
            rows.append({"english_clb": clb, "french_nclc": nclc, "total": calculate(p, rules).total})
    return pd.DataFrame(rows)


def _set_first_language_level(profile: Profile, level: Any) -> Profile:
    return with_language_level(profile, profile.first_language.language, int(level))


#: Factors available for the generic sweep: label -> (values, apply function).
SWEEP_FACTORS: dict[str, tuple[tuple[Any, ...], Callable[[Profile, Any], Profile]]] = {
    "Age": (tuple(range(18, 48)), lambda p, v: p.evolve(age=int(v))),
    "Canadian work experience (years)": (tuple(range(0, 6)), lambda p, v: p.evolve(canadian_work_years=int(v))),
    "Foreign work experience (years)": (tuple(range(0, 4)), lambda p, v: p.evolve(foreign_work_years=int(v))),
    "First official language CLB (all abilities)": (CLB_RANGE, _set_first_language_level),
    "Education level": (tuple(EducationLevel), lambda p, v: p.evolve(education=v)),
}


def factor_sweep(profile: Profile, rules: RuleSet, factor: str) -> pd.DataFrame:
    try:
        values, apply = SWEEP_FACTORS[factor]
    except KeyError as exc:
        raise ValueError(f"unknown factor {factor!r}; choose from {list(SWEEP_FACTORS)}") from exc
    df = sweep(profile, rules, "value", values, apply)
    if factor == "Education level":
        df["value"] = [v.label for v in values]
    return df


def compare_rule_sets(profile: Profile) -> pd.DataFrame:
    """Total and section scores for the same profile under every rule set."""
    rows = []
    for rules in RULE_SETS.values():
        rows.append({"rules_id": rules.id, "rules": rules.name, **_row(calculate(profile, rules))})
    return pd.DataFrame(rows)
