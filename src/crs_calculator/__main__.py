"""Command-line entry point: score a saved scenario/profile JSON file.

Usage::

    python -m crs_calculator examples/single_fsw.json [--rules 2026-11-03] [--json]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .calculator import calculate
from .rules import RULE_SETS, get_rules
from .serialization import scenario_from_json, scenario_to_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="crs-calculator", description=__doc__.splitlines()[0])
    parser.add_argument("scenario", type=Path, help="scenario or profile JSON file")
    parser.add_argument("--rules", choices=sorted(RULE_SETS), help="override the rule set stored in the file")
    parser.add_argument("--json", action="store_true", help="print the full scenario + result as JSON")
    args = parser.parse_args(argv)

    profile, rules_id = scenario_from_json(args.scenario.read_text(encoding="utf-8"))
    rules = get_rules(args.rules or rules_id)
    result = calculate(profile, rules)

    if args.json:
        print(scenario_to_json(profile, rules, result))
        return 0

    print(f"Rules: {rules.name}")
    for item in result.items:
        print(f"  {item.section.value[:2]} {item.factor:<55} {item.points:>4}  ({item.input})")
    for section, points in result.section_totals.items():
        print(f"{section.value:<40} {points:>4}")
    print(f"{'TOTAL':<40} {result.total:>4}")
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
