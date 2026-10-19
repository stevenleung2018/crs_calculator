# crs_calculator

Unofficial, **explainable and reproducible** calculator for the Express Entry
Comprehensive Ranking System (CRS), built with [Shiny for Python](https://shiny.posit.co/py/).
It is based on IRCC's [CRS tool](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/check-score.html)
and the published [CRS criteria](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/check-score/crs-criteria.html).

> **Disclaimer:** this is an educational tool and not affiliated with IRCC.
> Your official score is the one in your Express Entry profile.

## Features

- **Full CRS calculation**: core/human capital, spouse or common-law partner,
  skill transferability (with all sub-caps), and additional points.
- **Language test conversion**: IELTS General Training, CELPIP-General,
  PTE Core, TEF Canada and TCF Canada scores are converted to CLB/NCLC, or you
  can enter CLB/NCLC levels directly.
- **Two rule sets**:
  - `2025-03-25`: rules in force since job-offer points were removed (March 25, 2025).
  - `2026-11-03`: the new [Labour Market Integration factor](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/changes.html)
    (high-wage Canadian work experience **or** a high-wage job offer, whichever is higher).
  The rule set in force on today's date is selected by default.
- **Explainability**: every point is a line item showing your input, the points,
  the maximum and the rule that applied. Caps are shown as explicit negative
  rows, so the items always add up to the total.
- **Simulations with plots**:
  - Impact of French NCLC level (4 to 10+) on your total, by section, with an optional reference cut-off line.
  - English CLB x French NCLC heatmap.
  - One-factor sweeps (age, Canadian/foreign work experience, first-language CLB, education).
  - The same profile compared under each rule set.
- **Reproducibility**: download a scenario JSON (inputs, raw test scores, rule set,
  app version, SHA-256 fingerprint and full breakdown), reload it in the app, or
  score it from the command line.

## Quick start

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # create .venv and install dependencies
uv run shiny run --reload app.py         # open http://127.0.0.1:8000
```

Score a saved scenario without the UI:

```bash
uv run python -m crs_calculator examples/single_masters.json
uv run python -m crs_calculator examples/single_masters.json --rules 2026-11-03 --json
```

Use it as a library:

```python
from crs_calculator import EducationLevel, LanguageTest, Profile, RULES_2025_03, calculate
from crs_calculator.language import result_from_scores

english = result_from_scores(LanguageTest.CELPIP_GENERAL, {"speaking": 9, "listening": 9, "reading": 9, "writing": 9})
profile = Profile(
    age=29, education=EducationLevel.MASTERS, first_language=english, canadian_work_years=1, foreign_work_years=3
)
result = calculate(profile, RULES_2025_03)
print(result.total)  # 509
for item in result.items:
    print(item.section.value, item.factor, item.points, item.rule)
```

## Project layout

```
app.py                         # Shiny entry point (shiny run app.py)
src/crs_calculator/
  models.py                    # immutable, validated domain models (Profile, LanguageResult, ...)
  rules.py                     # versioned points tables, transcribed from IRCC pages
  language.py                  # test score -> CLB/NCLC conversion tables
  calculator.py                # pure calculate(profile, rules) -> CRSResult with line items
  simulation.py                # what-if sweeps returning pandas DataFrames
  serialization.py             # scenario JSON + SHA-256 fingerprint
  __main__.py                  # command-line interface
  app/                         # Shiny UI: inputs.py, plots.py, app.py, policy.md
examples/                      # sample scenario files
tests/                         # pytest suite (hand-checked against official tables)
```

The calculation engine has no dependency on Shiny, so it can be tested,
reused in notebooks, or wrapped in another interface.

## Development

```bash
uv run pytest --cov=crs_calculator   # tests + coverage
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

CI runs the same checks on Python 3.10, 3.12 and 3.13 (`.github/workflows/ci.yml`).

### Updating the rules

1. Add or edit tables in `src/crs_calculator/rules.py` and, for a new policy,
   a new `RuleSet` with its `effective_from` date.
2. Add hand-checked test cases in `tests/test_calculator.py`.
3. Update `src/crs_calculator/app/policy.md` with the change and its official source.

## Modelling assumptions

- You are scored "without a spouse" if your spouse/partner is not coming to Canada or is a Canadian citizen/PR.
- French bonus: 50 points when French is NCLC 7+ on all four abilities and English is CLB 5+ on all four;
  otherwise 25 points when French is NCLC 7+.
- Skill-transferability language thresholds use the first official language.
- High-wage occupation points need at least one year of Canadian work experience; the occupation's
  wage level (1.3x / 1.5x / 2x) comes from IRCC's list of eligible occupations and is entered by the user.

## Official sources

- [Express Entry: Check your score](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/check-score.html)
- [Comprehensive Ranking System (CRS) criteria](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/check-score/crs-criteria.html)
- [2026 changes to points for Canadian work experience and job offers](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/changes.html)
- [Backgrounder: Changes to Express Entry for high-wage occupations](https://www.canada.ca/en/immigration-refugees-citizenship/news/2026/10/changes-to-express-entry-for-high-wage-occupations.html)
- [Language testing equivalency tables](https://www.canada.ca/en/immigration-refugees-citizenship/services/immigrate-canada/express-entry/documents/language-requirements/language-testing.html)

## License

MIT, see [LICENSE](LICENSE).
