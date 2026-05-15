"""Standalone allometric scaling utilities.

This module intentionally has no dependency on NCA. It accepts species-level PK
parameters from any source and predicts a target species value, usually human.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence


PARAMETER_ALIASES = {
    "clearance": "clearance",
    "cl": "clearance",
    "cl/f": "clearance",
    "volume": "volume",
    "vd": "volume",
    "vz": "volume",
    "vz/f": "volume",
}

DEFAULT_EXPONENTS = {
    "clearance": 0.75,
    "volume": 1.0,
}


@dataclass(frozen=True)
class AllometrySpeciesInput:
    species: str
    body_weight_kg: float
    parameter: str
    value: float
    unit: str
    route: Optional[str] = None
    bioavailability_known: Optional[bool] = None


@dataclass(frozen=True)
class AllometryInput:
    rows: List[AllometrySpeciesInput]
    target_species: str = "human"
    target_body_weight_kg: float = 70.0
    fixed_exponent: Optional[float] = None


def normalize_parameter(parameter: str) -> str:
    key = (parameter or "").strip().lower()
    if key not in PARAMETER_ALIASES:
        raise ValueError("parameter must be clearance or volume.")
    return PARAMETER_ALIASES[key]


def _linear_regression(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float, float]:
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    ssxx = sum((x - xbar) ** 2 for x in xs)
    if ssxx <= 0:
        raise ValueError("multi-species allometry requires at least two distinct body weights.")
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / ssxx
    intercept = ybar - slope * xbar
    fitted = [intercept + slope * x for x in xs]
    ss_res = sum((y - yhat) ** 2 for y, yhat in zip(ys, fitted))
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    r_squared = 1.0 if ss_tot == 0 else max(0.0, 1.0 - ss_res / ss_tot)
    return intercept, slope, r_squared


def scale_allometry(inputs: AllometryInput) -> dict:
    if not inputs.rows:
        raise ValueError("at least one species row is required.")
    if inputs.target_body_weight_kg <= 0:
        raise ValueError("target_body_weight_kg must be greater than 0.")

    parameters = [normalize_parameter(row.parameter) for row in inputs.rows]
    parameter = parameters[0]
    if any(item != parameter for item in parameters):
        raise ValueError("all rows in one allometry request must use the same parameter type.")

    units = {(row.unit or "").strip() for row in inputs.rows}
    if len(units) != 1 or not next(iter(units)):
        raise ValueError("all rows must use one non-empty unit.")
    unit = next(iter(units))

    flags: List[str] = []
    for row in inputs.rows:
        if row.body_weight_kg <= 0:
            raise ValueError("body_weight_kg values must be greater than 0.")
        if row.value <= 0:
            raise ValueError("PK parameter values must be greater than 0.")
        if parameter == "clearance" and row.bioavailability_known is False:
            flags.append("clearance_may_be_apparent")

    if len(inputs.rows) == 1:
        row = inputs.rows[0]
        exponent = inputs.fixed_exponent if inputs.fixed_exponent is not None else DEFAULT_EXPONENTS[parameter]
        coefficient = row.value / (row.body_weight_kg ** exponent)
        predicted = coefficient * (inputs.target_body_weight_kg ** exponent)
        flags.append("single_species_exploratory")
        return {
            "parameter": parameter,
            "unit": unit,
            "target_species": inputs.target_species,
            "target_body_weight_kg": inputs.target_body_weight_kg,
            "predicted_value": predicted,
            "method": "single_species_fixed_exponent",
            "coefficient": coefficient,
            "exponent": exponent,
            "r_squared": None,
            "species_count": 1,
            "species_used": [row.species],
            "flags": sorted(set(flags)),
        }

    xs = [math.log(row.body_weight_kg) for row in inputs.rows]
    ys = [math.log(row.value) for row in inputs.rows]
    intercept, exponent, r_squared = _linear_regression(xs, ys)
    coefficient = math.exp(intercept)
    predicted = coefficient * (inputs.target_body_weight_kg ** exponent)
    if len(inputs.rows) < 3:
        flags.append("multi_species_fit_with_two_species")
    if r_squared < 0.8:
        flags.append("low_allometry_r_squared")

    return {
        "parameter": parameter,
        "unit": unit,
        "target_species": inputs.target_species,
        "target_body_weight_kg": inputs.target_body_weight_kg,
        "predicted_value": predicted,
        "method": "multi_species_log_log_allometry",
        "coefficient": coefficient,
        "exponent": exponent,
        "r_squared": r_squared,
        "species_count": len(inputs.rows),
        "species_used": [row.species for row in inputs.rows],
        "flags": sorted(set(flags)),
    }
