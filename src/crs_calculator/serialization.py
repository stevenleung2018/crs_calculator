"""JSON (de)serialization for reproducible, shareable calculations.

A saved scenario contains the profile, the rule-set id, the package version
and a SHA-256 fingerprint of the canonical profile JSON. Loading the same file
with the same package version always reproduces the same score.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from enum import Enum
from typing import Any

from . import __version__
from .calculator import CRSResult
from .models import (
    CanadianEducation,
    EducationLevel,
    HighWageLevel,
    Language,
    LanguageResult,
    LanguageTest,
    Profile,
    SpouseProfile,
)
from .rules import RuleSet

SCHEMA_VERSION = 1


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def profile_to_dict(profile: Profile) -> dict[str, Any]:
    return _plain(asdict(profile))


def _language_from_dict(data: dict[str, Any] | None) -> LanguageResult | None:
    if data is None:
        return None
    override = data.get("language_override")
    return LanguageResult(
        test=LanguageTest(data["test"]),
        speaking=int(data["speaking"]),
        listening=int(data["listening"]),
        reading=int(data["reading"]),
        writing=int(data["writing"]),
        language_override=Language(override) if override else None,
        raw_scores=tuple(float(v) for v in raw) if (raw := data.get("raw_scores")) else None,  # type: ignore[arg-type]
    )


def profile_from_dict(data: dict[str, Any]) -> Profile:
    spouse_data = data.get("spouse")
    spouse = None
    if spouse_data is not None:
        spouse = SpouseProfile(
            education=EducationLevel(spouse_data["education"]),
            canadian_work_years=int(spouse_data.get("canadian_work_years", 0)),
            language=_language_from_dict(spouse_data.get("language")),
        )
    first = _language_from_dict(data["first_language"])
    if first is None:
        raise ValueError("first_language is required")
    return Profile(
        age=int(data["age"]),
        education=EducationLevel(data["education"]),
        first_language=first,
        second_language=_language_from_dict(data.get("second_language")),
        canadian_work_years=int(data.get("canadian_work_years", 0)),
        foreign_work_years=int(data.get("foreign_work_years", 0)),
        certificate_of_qualification=bool(data.get("certificate_of_qualification", False)),
        canadian_education=CanadianEducation(data.get("canadian_education", "none")),
        provincial_nomination=bool(data.get("provincial_nomination", False)),
        sibling_in_canada=bool(data.get("sibling_in_canada", False)),
        spouse=spouse,
        high_wage_experience=HighWageLevel(data.get("high_wage_experience", "none")),
        job_offer=HighWageLevel(data.get("job_offer", "none")),
        notes=str(data.get("notes", "")),
    )


def fingerprint(profile: Profile) -> str:
    """Stable SHA-256 of the canonical profile JSON (notes excluded)."""
    data = profile_to_dict(profile)
    data.pop("notes", None)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def scenario_to_dict(profile: Profile, rules: RuleSet, result: CRSResult | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "app_version": __version__,
        "rules_id": rules.id,
        "profile_sha256": fingerprint(profile),
        "profile": profile_to_dict(profile),
    }
    if result is not None:
        payload["result"] = {
            "total": result.total,
            "sections": {s.value: v for s, v in result.section_totals.items()},
            "warnings": list(result.warnings),
            "items": [
                {
                    "section": i.section.value,
                    "factor": i.factor,
                    "input": i.input,
                    "points": i.points,
                    "max_points": i.max_points,
                    "rule": i.rule,
                    "source_url": i.source_url,
                }
                for i in result.items
            ],
        }
    return payload


def scenario_to_json(profile: Profile, rules: RuleSet, result: CRSResult | None = None) -> str:
    return json.dumps(scenario_to_dict(profile, rules, result), indent=2, sort_keys=False)


def scenario_from_json(text: str) -> tuple[Profile, str]:
    """Parse a scenario (or a bare profile) and return ``(profile, rules_id)``."""
    data = json.loads(text)
    if "profile" in data:
        version = data.get("schema_version", SCHEMA_VERSION)
        if version > SCHEMA_VERSION:
            raise ValueError(f"scenario schema {version} is newer than supported ({SCHEMA_VERSION})")
        return profile_from_dict(data["profile"]), data.get("rules_id", "2025-03-25")
    return profile_from_dict(data), "2025-03-25"
