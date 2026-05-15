from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.allometry import AllometryInput, AllometrySpeciesInput, scale_allometry  # noqa: E402
from app.nca import ConcentrationTimePoint, NCAProfileInput, calculate_profile_nca  # noqa: E402


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "literature"


def _load_fixture(filename: str):
    with (FIXTURE_DIR / filename).open("r", encoding="utf-8") as handle:
        return json.load(handle)


NCA_CASES = _load_fixture("nca_cases.json")
ALLOMETRY_CASES = _load_fixture("allometry_cases.json")


def _assert_relative(actual: float, expected: float, tolerance: float, label: str, case: dict) -> None:
    assert actual == pytest.approx(expected, rel=tolerance), (
        f"{case['case_id']} {label} mismatch. "
        f"actual={actual:.8g}, expected={expected:.8g}, rel_tol={tolerance}. "
        f"Source: {case['source']}"
    )


def _assert_absolute(actual: float, expected: float, tolerance: float, label: str, case: dict) -> None:
    assert actual == pytest.approx(expected, abs=tolerance), (
        f"{case['case_id']} {label} mismatch. "
        f"actual={actual:.8g}, expected={expected:.8g}, abs_tol={tolerance}. "
        f"Source: {case['source']}"
    )


@pytest.mark.parametrize("case", NCA_CASES, ids=lambda item: item["case_id"])
def test_literature_nca_case_studies(case):
    profile = case["profile"]
    result = calculate_profile_nca(
        NCAProfileInput(
            compound_id=profile.get("compound_id"),
            study_id=profile.get("study_id"),
            subject_id=profile.get("subject_id"),
            species=profile.get("species"),
            matrix=profile["matrix"],
            route=profile["route"],
            dose=profile["dose"],
            dose_unit=profile["dose_unit"],
            time_unit=profile["time_unit"],
            concentration_unit=profile["concentration_unit"],
            observations=[
                ConcentrationTimePoint(
                    time=row["time"],
                    concentration=row["concentration"],
                )
                for row in profile["observations"]
            ],
            terminal_times=profile.get("terminal_times"),
        )
    )

    expected = case["reported_outputs"]
    tolerances = case["tolerances"]
    for parameter, tolerance in tolerances["relative"].items():
        _assert_relative(result[parameter], expected[parameter], tolerance, parameter, case)
    for parameter, tolerance in tolerances.get("absolute", {}).items():
        _assert_absolute(result[parameter], expected[parameter], tolerance, parameter, case)

    assert result["matrix"] in {"plasma", "blood", "serum"}
    assert result["route"] == "extravascular"
    assert result["clearance_label"] == "CL/F"


@pytest.mark.parametrize("case", ALLOMETRY_CASES, ids=lambda item: item["case_id"])
def test_literature_allometry_case_studies(case):
    result = scale_allometry(
        AllometryInput(
            rows=[
                AllometrySpeciesInput(
                    species=row["species"],
                    body_weight_kg=row["body_weight_kg"],
                    parameter=row["parameter"],
                    value=row["value"],
                    unit=row["unit"],
                )
                for row in case["rows"]
            ],
            target_species="human",
            target_body_weight_kg=case["target_body_weight_kg"],
        )
    )

    expected = case["reported_outputs"]
    for parameter, tolerance in case["tolerances"]["relative"].items():
        _assert_relative(result[parameter], expected[parameter], tolerance, parameter, case)

    assert result["method"] == "multi_species_log_log_allometry"
    assert result["parameter"] == "clearance"
    assert result["species_count"] == len(case["rows"])
