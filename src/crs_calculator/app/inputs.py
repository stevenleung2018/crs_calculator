"""UI builders and readers for the profile inputs (keeps app.py small)."""

from __future__ import annotations

from typing import Any

from shiny import ui

from ..language import SCORE_SPECS, TEST_LABELS, result_from_scores
from ..models import (
    ABILITIES,
    CanadianEducation,
    EducationLevel,
    HighWageLevel,
    Language,
    LanguageResult,
    LanguageTest,
    Profile,
    SpouseProfile,
)

NO_TEST = "none"
LANGUAGE_SLOTS = ("lang1", "lang2", "spouse_lang")

#: Default raw scores shown when a test is selected (CLB 9 for CELPIP, CLB 7 otherwise).
DEFAULT_SCORES: dict[LanguageTest, dict[str, float]] = {
    LanguageTest.CELPIP_GENERAL: dict.fromkeys(ABILITIES, 9),
    LanguageTest.IELTS_GENERAL: dict.fromkeys(ABILITIES, 6.0),
    LanguageTest.PTE_CORE: {"speaking": 68, "listening": 60, "reading": 60, "writing": 69},
    LanguageTest.TEF_CANADA: {"speaking": 310, "listening": 249, "reading": 207, "writing": 310},
    LanguageTest.TCF_CANADA: {"speaking": 10, "listening": 458, "reading": 453, "writing": 10},
    LanguageTest.CLB_DIRECT: dict.fromkeys(ABILITIES, 7),
}

EDUCATION_CHOICES = {e.value: e.label for e in EducationLevel}
CANADIAN_EDUCATION_CHOICES = {e.value: e.label for e in CanadianEducation}
HIGH_WAGE_CHOICES = {h.value: h.label for h in HighWageLevel}
CANADIAN_YEARS = {
    "0": "None or less than a year",
    **{str(y): f"{y} year{'s' if y > 1 else ''}" for y in range(1, 5)},
    "5": "5 years or more",
}
FOREIGN_YEARS = {"0": "None or less than a year", "1": "1 year", "2": "2 years", "3": "3 years or more"}
TEST_CHOICES = {t.value: TEST_LABELS[t] for t in TEST_LABELS}


def language_block(slot: str, title: str, *, optional: bool, default_test: LanguageTest) -> ui.TagList:
    """Test selector + four score inputs + live CLB readout for one test slot."""
    choices = ({NO_TEST: "No test / not applicable"} if optional else {}) | TEST_CHOICES
    selected = NO_TEST if optional else default_test.value
    spec_test = default_test
    defaults = DEFAULT_SCORES[spec_test]
    score_inputs = [
        ui.input_numeric(
            f"{slot}_{a}",
            a.capitalize(),
            value=defaults[a],
            min=SCORE_SPECS[spec_test][a].minimum,
            max=SCORE_SPECS[spec_test][a].maximum,
            step=SCORE_SPECS[spec_test][a].step,
        )
        for a in ABILITIES
    ]
    scores = ui.layout_column_wrap(*score_inputs, width=1 / 2, gap="0.5rem")
    if optional:
        scores = ui.panel_conditional(f"input.{slot}_test !== '{NO_TEST}'", scores)
    extra: list[Any] = []
    if slot == "lang1":
        extra.append(
            ui.panel_conditional(
                f"input.{slot}_test === '{LanguageTest.CLB_DIRECT.value}'",
                ui.input_radio_buttons(
                    "lang1_direct_language",
                    "Language of these levels",
                    {Language.ENGLISH.value: "English", Language.FRENCH.value: "French"},
                    inline=True,
                ),
            )
        )
    return ui.TagList(
        ui.input_select(f"{slot}_test", title, choices, selected=selected),
        *extra,
        scores,
        ui.output_ui(f"{slot}_clb"),
    )


def sidebar_inputs(default_rules_id: str, rule_choices: dict[str, str]) -> list[Any]:
    return [
        ui.input_radio_buttons("rules_id", "Rule set", rule_choices, selected=default_rules_id),
        ui.accordion(
            ui.accordion_panel(
                "1. Marital status & age",
                ui.input_select(
                    "marital",
                    "Marital status",
                    {
                        "single": "Single, divorced, separated or widowed",
                        "partnered": "Married or common-law partner",
                    },
                ),
                ui.panel_conditional(
                    "input.marital === 'partnered'",
                    ui.input_checkbox("spouse_is_canadian", "Spouse/partner is a Canadian citizen or PR", False),
                    ui.input_checkbox("spouse_accompanying", "Spouse/partner will come with you to Canada", True),
                ),
                ui.input_numeric("age", "Age (at invitation, or current age)", value=29, min=16, max=70, step=1),
            ),
            ui.accordion_panel(
                "2. Education",
                ui.input_select(
                    "education",
                    "Highest level of education (Canadian or ECA)",
                    EDUCATION_CHOICES,
                    selected=EducationLevel.BACHELORS.value,
                ),
                ui.input_select(
                    "canadian_education", "Post-secondary credential earned in Canada", CANADIAN_EDUCATION_CHOICES
                ),
            ),
            ui.accordion_panel(
                "3. Official languages",
                language_block(
                    "lang1", "First official language test", optional=False, default_test=LanguageTest.CELPIP_GENERAL
                ),
                ui.hr(),
                language_block(
                    "lang2", "Second official language test", optional=True, default_test=LanguageTest.TEF_CANADA
                ),
            ),
            ui.accordion_panel(
                "4. Work experience",
                ui.input_select(
                    "canadian_work_years", "Skilled Canadian work, last 10 years", CANADIAN_YEARS, selected="1"
                ),
                ui.input_select(
                    "foreign_work_years", "Foreign skilled work, last 10 years", FOREIGN_YEARS, selected="3"
                ),
                ui.input_checkbox("coq", "Certificate of qualification in a trade", False),
            ),
            ui.accordion_panel(
                "5. High-wage occupation & job offer",
                ui.markdown("Only scored under the **November 3, 2026** rule set."),
                ui.input_select(
                    "high_wage_experience", "12+ months Canadian work in a high-wage occupation", HIGH_WAGE_CHOICES
                ),
                ui.input_select("job_offer", "Qualifying job offer (no LMIA needed)", HIGH_WAGE_CHOICES),
            ),
            ui.accordion_panel(
                "6. Additional points",
                ui.input_checkbox("pnp", "Provincial or territorial nomination", False),
                ui.input_checkbox("sibling", "Brother or sister in Canada (citizen/PR, 18+)", False),
            ),
            ui.accordion_panel(
                "7. Spouse or partner",
                ui.panel_conditional(
                    "input.marital === 'partnered' && input.spouse_accompanying && !input.spouse_is_canadian",
                    ui.input_select(
                        "spouse_education",
                        "Spouse's highest education",
                        EDUCATION_CHOICES,
                        selected=EducationLevel.SECONDARY.value,
                    ),
                    ui.input_select(
                        "spouse_canadian_work_years",
                        "Spouse's Canadian work, last 10 years",
                        CANADIAN_YEARS,
                        selected="0",
                    ),
                    language_block(
                        "spouse_lang", "Spouse's language test", optional=True, default_test=LanguageTest.CELPIP_GENERAL
                    ),
                ),
                ui.panel_conditional(
                    "!(input.marital === 'partnered' && input.spouse_accompanying && !input.spouse_is_canadian)",
                    ui.markdown("Not applicable: you are scored as single."),
                ),
            ),
            id="input_sections",
            open=["1. Marital status & age", "3. Official languages"],
            multiple=True,
        ),
    ]


def read_language(input: Any, slot: str, direct_language: Language) -> LanguageResult | None:
    """Read one language slot; ``None`` when no test is selected."""
    test_value = input[f"{slot}_test"]()
    if test_value == NO_TEST:
        return None
    test = LanguageTest(test_value)
    scores: dict[str, float] = {}
    for ability in ABILITIES:
        value = input[f"{slot}_{ability}"]()
        if value is None:
            raise ValueError(f"enter a {ability} score for the {slot.replace('_', ' ')} test")
        scores[ability] = float(value)
    return result_from_scores(test, scores, language=direct_language)


def _other(language: Language) -> Language:
    return Language.FRENCH if language is Language.ENGLISH else Language.ENGLISH


def _first_language(input: Any) -> Language:
    test = LanguageTest(input.lang1_test())
    return test.language or Language(input.lang1_direct_language())


def direct_language_for(input: Any, slot: str) -> Language:
    """Language implied by direct CLB entry in ``slot``.

    The second official language is always the opposite of the first; the
    spouse's language does not affect points, so English is used.
    """
    if slot == "lang1":
        return _first_language(input)
    if slot == "lang2":
        return _other(_first_language(input))
    return Language.ENGLISH


def read_profile(input: Any) -> Profile:
    """Translate the current UI state into a validated :class:`Profile`."""
    first = read_language(input, "lang1", direct_language_for(input, "lang1"))
    if first is None:  # pragma: no cover - the first test is never optional
        raise ValueError("a first official language test is required")
    second = read_language(input, "lang2", direct_language_for(input, "lang2"))

    spouse = None
    if input.marital() == "partnered" and input.spouse_accompanying() and not input.spouse_is_canadian():
        spouse = SpouseProfile(
            education=EducationLevel(input.spouse_education()),
            canadian_work_years=int(input.spouse_canadian_work_years()),
            language=read_language(input, "spouse_lang", direct_language_for(input, "spouse_lang")),
        )
    age = input.age()
    if age is None:
        raise ValueError("enter your age")
    return Profile(
        age=int(age),
        education=EducationLevel(input.education()),
        first_language=first,
        second_language=second,
        canadian_work_years=int(input.canadian_work_years()),
        foreign_work_years=int(input.foreign_work_years()),
        certificate_of_qualification=bool(input.coq()),
        canadian_education=CanadianEducation(input.canadian_education()),
        provincial_nomination=bool(input.pnp()),
        sibling_in_canada=bool(input.sibling()),
        spouse=spouse,
        high_wage_experience=HighWageLevel(input.high_wage_experience()),
        job_offer=HighWageLevel(input.job_offer()),
    )
