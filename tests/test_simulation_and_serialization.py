from __future__ import annotations

import json
from datetime import date

from crs_calculator import RULES_2025_03, RULES_2026_11, Profile, calculate, rules_in_force
from crs_calculator.__main__ import main
from crs_calculator.serialization import fingerprint, scenario_from_json, scenario_to_json
from crs_calculator.simulation import SWEEP_FACTORS, compare_rule_sets, factor_sweep, french_nclc_sweep, language_grid


def test_french_sweep_is_monotonic_with_bonus_jump(single_masters: Profile) -> None:
    df = french_nclc_sweep(single_masters, RULES_2025_03)
    assert list(df["nclc"]) == list(range(3, 11))
    assert df["total"].is_monotonic_increasing
    by_level = df.set_index("nclc")
    assert by_level.loc[6, "french_bonus"] == 0
    assert by_level.loc[7, "french_bonus"] == 50
    # NCLC 3 adds nothing to the baseline profile (which has no French).
    assert by_level.loc[3, "change_vs_baseline"] == 0


def test_language_grid_shape(single_masters: Profile) -> None:
    grid = language_grid(single_masters, RULES_2025_03)
    assert len(grid) == 64


def test_all_factor_sweeps_run(single_masters: Profile) -> None:
    for factor in SWEEP_FACTORS:
        assert not factor_sweep(single_masters, RULES_2026_11, factor).empty


def test_compare_rule_sets(single_masters: Profile) -> None:
    assert set(compare_rule_sets(single_masters)["rules_id"]) == {"2025-03-25", "2026-11-03"}


def test_scenario_round_trip_reproduces_score(single_masters: Profile) -> None:
    text = scenario_to_json(single_masters, RULES_2026_11, calculate(single_masters, RULES_2026_11))
    profile, rules_id = scenario_from_json(text)
    assert profile == single_masters
    assert rules_id == "2026-11-03"
    assert json.loads(text)["profile_sha256"] == fingerprint(profile)


def test_rules_in_force_by_date() -> None:
    assert rules_in_force(date(2026, 10, 19)) is RULES_2025_03
    assert rules_in_force(date(2026, 11, 3)) is RULES_2026_11


def test_cli(tmp_path, single_masters: Profile, capsys) -> None:
    path = tmp_path / "scenario.json"
    path.write_text(scenario_to_json(single_masters, RULES_2025_03))
    assert main([str(path)]) == 0
    assert "509" in capsys.readouterr().out


def test_raw_scores_survive_round_trip() -> None:
    from crs_calculator import EducationLevel, LanguageTest
    from crs_calculator.language import result_from_scores

    english = result_from_scores(
        LanguageTest.IELTS_GENERAL, {"speaking": 7.0, "listening": 8.5, "reading": 6.5, "writing": 6.0}
    )
    profile = Profile(age=33, education=EducationLevel.MASTERS, first_language=english)
    restored, _ = scenario_from_json(scenario_to_json(profile, RULES_2025_03))
    assert restored.first_language.raw_scores == (7.0, 8.5, 6.5, 6.0)
    assert fingerprint(restored) == fingerprint(profile)
