"""Registry of per-assessment-year rule sets.

Each AY is a hand-written module (ay2025_26.py, ay2026_27.py, ...). Nothing is
extrapolated automatically for a future year — add a new module when the Budget
changes the numbers, and cite the source (Finance Act / CBDT notification) in a
comment at the top of that module.
"""

from .ay2025_26 import RULES as AY_2025_26
from .ay2026_27 import RULES as AY_2026_27
from .base import AssessmentYearRules

_REGISTRY: dict[str, AssessmentYearRules] = {
    "2025-26": AY_2025_26,
    "2026-27": AY_2026_27,
}


def get_rules(assessment_year: str) -> AssessmentYearRules:
    try:
        return _REGISTRY[assessment_year]
    except KeyError as e:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"No rule set for AY {assessment_year}. Available: {available}. "
            "Add src/india_tax_guru/rules/ay<yy>_<yy>.py and register it here."
        ) from e


def available_years() -> list[str]:
    return sorted(_REGISTRY)
