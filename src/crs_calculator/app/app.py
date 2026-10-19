"""Shiny for Python app: explainable CRS calculator with simulations."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from shiny import App, Inputs, Outputs, Session, reactive, render, req, ui

from .. import __version__
from ..calculator import CRSResult, Section, calculate
from ..language import SCORE_SPECS
from ..models import ABILITIES, LanguageResult, LanguageTest, Profile
from ..rules import RULE_SETS, get_rules, rules_in_force
from ..serialization import fingerprint, scenario_from_json, scenario_to_json
from ..simulation import SWEEP_FACTORS, compare_rule_sets, factor_sweep, french_nclc_sweep, language_grid
from . import plots
from .inputs import (
    DEFAULT_SCORES,
    LANGUAGE_SLOTS,
    NO_TEST,
    direct_language_for,
    read_language,
    read_profile,
    sidebar_inputs,
)

POLICY_MD = (Path(__file__).parent / "policy.md").read_text(encoding="utf-8")
RULE_CHOICES = {r.id: r.name for r in RULE_SETS.values()}


COLUMN_LABELS = {
    "total": "Total",
    "change_vs_baseline": "Change vs current",
    "french_bonus": "French bonus",
    "rules": "Rule set",
}


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    """Drop all-zero section columns and use readable headers for display."""
    sections = [s.value for s in Section]
    empty = [c for c in df.columns if c in sections and not df[c].any()]
    return df.drop(columns=empty).rename(columns=COLUMN_LABELS)


def _score_box(title: str, output_id: str, theme: str = "primary") -> ui.Tag:
    return ui.value_box(title, ui.output_text(output_id), theme=theme)


APP_CSS = """
.policy table { width: 100%; margin-bottom: 1rem; border-collapse: collapse; }
.policy th, .policy td { border-bottom: 1px solid var(--bs-border-color); padding: .4rem .6rem; vertical-align: top; }
.policy th { background: var(--bs-tertiary-bg); }
.policy h3 { margin-top: 1.25rem; font-size: 1.35rem; }
"""

app_ui = ui.page_sidebar(
    ui.sidebar(
        *sidebar_inputs(rules_in_force(date.today()).id, RULE_CHOICES),
        width=400,
        title="Your profile",
    ),
    ui.navset_card_underline(
        ui.nav_panel(
            "Score",
            ui.layout_column_wrap(
                _score_box("Total CRS score", "total"),
                _score_box("Core, spouse & labour market", "core_total", "bg-gradient-blue-teal"),
                _score_box("Skill transferability", "transfer_total", "bg-gradient-orange-yellow"),
                _score_box("Additional", "additional_total", "bg-gradient-red-orange"),
                width=1 / 4,
                fill=False,
            ),
            ui.output_ui("warnings"),
            ui.output_plot("section_plot", height="260px"),
            ui.h5("Line-by-line explanation"),
            ui.output_data_frame("breakdown"),
        ),
        ui.nav_panel(
            "Simulation",
            ui.navset_pill(
                ui.nav_panel(
                    "French NCLC impact",
                    ui.p(
                        "Your profile is held constant while French is set to each NCLC level on all four "
                        "abilities (added as your second official language if you have no French test)."
                    ),
                    ui.input_numeric("cutoff", "Reference cut-off to compare against (0 = hide)", 0, min=0, max=1200),
                    ui.output_plot("french_plot", height="420px"),
                    ui.output_data_frame("french_table"),
                ),
                ui.nav_panel(
                    "English x French grid",
                    ui.p("Total CRS for every combination of English CLB and French NCLC (uniform abilities)."),
                    ui.output_plot("grid_plot", height="500px"),
                ),
                ui.nav_panel(
                    "One-factor sweep",
                    ui.input_select("sweep_factor", "Factor to vary", list(SWEEP_FACTORS)),
                    ui.output_plot("sweep_plot", height="400px"),
                    ui.output_data_frame("sweep_table"),
                ),
                ui.nav_panel(
                    "Rule-set comparison",
                    ui.p("The same profile scored under each rule set modelled by the app."),
                    ui.output_data_frame("rules_table"),
                ),
            ),
        ),
        ui.nav_panel(
            "Reproducibility",
            ui.markdown(
                "Save the exact inputs, rule set and result as JSON. Re-load the file here, or score it "
                "from the command line with `python -m crs_calculator scenario.json`."
            ),
            ui.layout_columns(
                ui.download_button("download", "Download scenario JSON"),
                ui.input_file("upload", "Load scenario JSON", accept=[".json"], multiple=False),
                col_widths=(4, 8),
            ),
            ui.output_ui("restore_status"),
            ui.output_code("fingerprint_text"),
            ui.output_code("scenario_json"),
        ),
        ui.nav_panel("Policy & sources", ui.div(ui.markdown(POLICY_MD), class_="policy")),
    ),
    ui.head_content(ui.tags.style(APP_CSS)),
    title=f"Express Entry CRS calculator (unofficial) v{__version__}",
    fillable=False,
)


def server(input: Inputs, output: Outputs, session: Session) -> None:
    #: (test, scores) waiting to be applied after a scenario is loaded, per slot.
    pending_scores: dict[str, tuple[LanguageTest, dict[str, float]]] = {}
    restore_message = reactive.value("")

    # --- keep score inputs consistent with the chosen test -----------------
    def _register_test_observer(slot: str) -> None:
        @reactive.effect
        @reactive.event(input[f"{slot}_test"], ignore_init=True)
        def _update_score_inputs() -> None:
            test_value = input[f"{slot}_test"]()
            if test_value == NO_TEST:
                return
            test = LanguageTest(test_value)
            pending = pending_scores.pop(slot, None)
            values = pending[1] if pending and pending[0] is test else DEFAULT_SCORES[test]
            for ability in ABILITIES:
                spec = SCORE_SPECS[test][ability]
                ui.update_numeric(
                    f"{slot}_{ability}", value=values[ability], min=spec.minimum, max=spec.maximum, step=spec.step
                )

        @output(id=f"{slot}_clb")
        @render.ui
        def _clb_readout() -> ui.Tag | None:
            if input[f"{slot}_test"]() == NO_TEST:
                return None
            try:
                result = read_language(input, slot, direct_language_for(input, slot))
            except ValueError as exc:
                return ui.div(str(exc), class_="text-danger small")
            assert result is not None
            levels = " · ".join(f"{a.capitalize()} {result.levels[a]}" for a in ABILITIES)
            return ui.div(f"{result.language.value.capitalize()} CLB/NCLC: {levels}", class_="text-muted small mb-2")

    for slot in LANGUAGE_SLOTS:
        _register_test_observer(slot)

    # --- core reactive pipeline -------------------------------------------
    @reactive.calc
    def profile_or_error() -> Profile | str:
        try:
            return read_profile(input)
        except ValueError as exc:
            return str(exc)

    @reactive.calc
    def profile() -> Profile:
        value = profile_or_error()
        req(isinstance(value, Profile))
        assert isinstance(value, Profile)
        return value

    @reactive.calc
    def rules():
        return get_rules(input.rules_id())

    @reactive.calc
    def result() -> CRSResult:
        return calculate(profile(), rules())

    # --- Score tab ----------------------------------------------------------
    @render.text
    def total() -> str:
        return str(result().total)

    @render.text
    def core_total() -> str:
        r = result()
        return str(sum(r.section_total(s) for s in (Section.CORE, Section.SPOUSE, Section.LABOUR_MARKET)))

    @render.text
    def transfer_total() -> str:
        return str(result().section_total(Section.TRANSFERABILITY))

    @render.text
    def additional_total() -> str:
        return str(result().section_total(Section.ADDITIONAL))

    @render.ui
    def warnings() -> ui.TagList:
        value = profile_or_error()
        messages: list[ui.Tag] = []
        if isinstance(value, str):
            messages.append(ui.div(f"Input error: {value}", class_="alert alert-danger"))
        else:
            messages += [ui.div(w, class_="alert alert-warning py-2") for w in result().warnings]
            messages.append(ui.div(rules().description, class_="text-muted small mb-2"))
        return ui.TagList(*messages)

    @render.plot
    def section_plot():
        return plots.section_bars(result())

    @render.data_frame
    def breakdown():
        rows = [
            {
                "Section": i.section.value,
                "Factor": i.factor,
                "Your input": i.input,
                "Points": i.points,
                "Max": "" if i.max_points is None else i.max_points,
                "How it was scored": i.rule,
            }
            for i in result().items
        ]
        return render.DataGrid(pd.DataFrame(rows), height="520px", width="100%")

    # --- Simulation tab -----------------------------------------------------
    @reactive.calc
    def french_df() -> pd.DataFrame:
        return french_nclc_sweep(profile(), rules())

    @render.plot
    def french_plot():
        cutoff = input.cutoff() or None
        return plots.french_sweep(french_df(), result().total, int(cutoff) if cutoff else None)

    @render.data_frame
    def french_table():
        df = french_df()
        return render.DataGrid(_tidy(df.rename(columns={"nclc": "French NCLC"})), width="100%")

    @render.plot
    def grid_plot():
        return plots.language_heatmap(language_grid(profile(), rules()))

    @reactive.calc
    def sweep_df() -> pd.DataFrame:
        return factor_sweep(profile(), rules(), input.sweep_factor())

    @render.plot
    def sweep_plot():
        return plots.factor_line(sweep_df(), input.sweep_factor(), result().total)

    @render.data_frame
    def sweep_table():
        return render.DataGrid(_tidy(sweep_df().rename(columns={"value": input.sweep_factor()})), width="100%")

    @render.data_frame
    def rules_table():
        return render.DataGrid(_tidy(compare_rule_sets(profile()).drop(columns="rules_id")), width="100%")

    # --- Reproducibility tab ------------------------------------------------
    @render.download_button(filename=lambda: f"crs-scenario-{date.today().isoformat()}.json")
    def download():
        yield scenario_to_json(profile(), rules(), result())

    @render.code
    def fingerprint_text() -> str:
        return f"Profile SHA-256: {fingerprint(profile())}\nRule set: {rules().id}   App version: {__version__}"

    @render.code
    def scenario_json() -> str:
        return scenario_to_json(profile(), rules())

    @render.ui
    def restore_status() -> ui.Tag | None:
        message = restore_message()
        return ui.div(message, class_="alert alert-info py-2") if message else None

    @reactive.effect
    @reactive.event(input.upload)
    def _restore() -> None:
        files = input.upload()
        if not files:
            return
        try:
            loaded, rules_id = scenario_from_json(Path(files[0]["datapath"]).read_text(encoding="utf-8"))
            get_rules(rules_id)
        except (ValueError, KeyError, TypeError) as exc:
            restore_message.set(f"Could not load scenario: {exc}")
            return
        _apply_profile(loaded, rules_id)
        restore_message.set(f"Loaded scenario (profile SHA-256 {fingerprint(loaded)[:12]}...).")

    def _apply_language(slot: str, result_: LanguageResult | None) -> None:
        if result_ is None:
            ui.update_select(f"{slot}_test", selected=NO_TEST)
            return
        # Restore the original raw scores when available; otherwise enter CLB levels directly.
        test: LanguageTest
        if result_.raw_scores is not None and result_.test is not LanguageTest.CLB_DIRECT:
            test = result_.test
            values = dict(zip(ABILITIES, result_.raw_scores, strict=True))
        else:
            test = LanguageTest.CLB_DIRECT
            values = {a: float(min(getattr(result_, a), 10)) for a in ABILITIES}
        pending_scores[slot] = (test, values)
        ui.update_select(f"{slot}_test", selected=test.value)
        for ability in ABILITIES:  # applies immediately when the test is unchanged
            spec = SCORE_SPECS[test][ability]
            ui.update_numeric(
                f"{slot}_{ability}", value=values[ability], min=spec.minimum, max=spec.maximum, step=spec.step
            )

    def _apply_profile(p: Profile, rules_id: str) -> None:
        ui.update_radio_buttons("rules_id", selected=rules_id)
        ui.update_select("marital", selected="partnered" if p.spouse else "single")
        ui.update_checkbox("spouse_accompanying", value=True)
        ui.update_checkbox("spouse_is_canadian", value=False)
        ui.update_numeric("age", value=p.age)
        ui.update_select("education", selected=p.education.value)
        ui.update_select("canadian_education", selected=p.canadian_education.value)
        ui.update_radio_buttons("lang1_direct_language", selected=p.first_language.language.value)
        _apply_language("lang1", p.first_language)
        _apply_language("lang2", p.second_language)
        ui.update_select("canadian_work_years", selected=str(p.canadian_work_years))
        ui.update_select("foreign_work_years", selected=str(p.foreign_work_years))
        ui.update_checkbox("coq", value=p.certificate_of_qualification)
        ui.update_select("high_wage_experience", selected=p.high_wage_experience.value)
        ui.update_select("job_offer", selected=p.job_offer.value)
        ui.update_checkbox("pnp", value=p.provincial_nomination)
        ui.update_checkbox("sibling", value=p.sibling_in_canada)
        if p.spouse is not None:
            ui.update_select("spouse_education", selected=p.spouse.education.value)
            ui.update_select("spouse_canadian_work_years", selected=str(p.spouse.canadian_work_years))
            _apply_language("spouse_lang", p.spouse.language)


app = App(app_ui, server)
