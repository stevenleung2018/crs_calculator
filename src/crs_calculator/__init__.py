"""Unofficial, explainable Express Entry CRS calculator."""

__version__ = "0.1.0"

from .calculator import CRSResult, LineItem, Section, calculate
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
from .rules import RULE_SETS, RULES_2025_03, RULES_2026_11, RuleSet, get_rules, rules_in_force

__all__ = [
    "RULES_2025_03",
    "RULES_2026_11",
    "RULE_SETS",
    "CRSResult",
    "CanadianEducation",
    "EducationLevel",
    "HighWageLevel",
    "Language",
    "LanguageResult",
    "LanguageTest",
    "LineItem",
    "Profile",
    "RuleSet",
    "Section",
    "SpouseProfile",
    "__version__",
    "calculate",
    "get_rules",
    "rules_in_force",
]
