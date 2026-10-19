from __future__ import annotations

from matplotlib.figure import Figure

from crs_calculator import RULES_2025_03, Profile, calculate
from crs_calculator.app import app, plots
from crs_calculator.simulation import factor_sweep, french_nclc_sweep, language_grid


def test_app_object_builds() -> None:
    assert app is not None


def test_plots_return_figures(single_masters: Profile) -> None:
    result = calculate(single_masters, RULES_2025_03)
    figures = [
        plots.section_bars(result),
        plots.french_sweep(french_nclc_sweep(single_masters, RULES_2025_03), result.total, cutoff=500),
        plots.language_heatmap(language_grid(single_masters, RULES_2025_03)),
        plots.factor_line(factor_sweep(single_masters, RULES_2025_03, "Education level"), "Education level", 500),
    ]
    assert all(isinstance(f, Figure) for f in figures)
