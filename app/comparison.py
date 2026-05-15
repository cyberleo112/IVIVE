"""Observed-vs-predicted PK parameter comparison helpers."""

from __future__ import annotations

from typing import Iterable, List


PARAMETER_ALIASES = {
    "clearance": "clearance",
    "cl": "clearance",
    "cl/f": "clearance",
    "volume": "volume",
    "vd": "volume",
    "vz": "volume",
    "vz/f": "volume",
    "auc": "auc",
    "auclast": "auc",
    "auc0-t": "auc",
    "aucinf": "aucinf",
    "auc0-inf": "aucinf",
    "cmax": "cmax",
    "tmax": "tmax",
    "half_life": "half_life",
    "t1/2": "half_life",
    "kel": "kel",
    "lambda_z": "kel",
}


def normalize_parameter(parameter: str) -> str:
    key = (parameter or "").strip().lower()
    return PARAMETER_ALIASES.get(key, key)


def _clean_optional(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _compatible(observed: dict, predicted: dict) -> bool:
    if normalize_parameter(observed["parameter"]) != normalize_parameter(predicted["parameter"]):
        return False
    if observed["unit"].strip() != predicted["unit"].strip():
        return False
    for key in ("compound_id", "species"):
        left = _clean_optional(observed.get(key))
        right = _clean_optional(predicted.get(key))
        if left and right and left.lower() != right.lower():
            return False
    return True


def compare_predictions(observed_rows: Iterable[dict], predicted_rows: Iterable[dict]) -> List[dict]:
    comparisons: List[dict] = []
    for observed in observed_rows:
        for predicted in predicted_rows:
            if not _compatible(observed, predicted):
                continue
            observed_value = float(observed["value"])
            predicted_value = float(predicted["value"])
            ratio = predicted_value / observed_value
            fold_error = max(ratio, 1.0 / ratio)
            comparisons.append({
                "compound_id": observed.get("compound_id") or predicted.get("compound_id"),
                "species": observed.get("species") or predicted.get("species"),
                "parameter": normalize_parameter(observed["parameter"]),
                "unit": observed["unit"],
                "observed_value": observed_value,
                "predicted_value": predicted_value,
                "observed_method": observed.get("method"),
                "predicted_method": predicted.get("method"),
                "predicted_to_observed_ratio": ratio,
                "fold_error": fold_error,
                "percent_error": (ratio - 1.0) * 100.0,
                "within_2_fold": fold_error <= 2.0,
                "within_3_fold": fold_error <= 3.0,
            })
    return comparisons
