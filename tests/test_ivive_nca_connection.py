from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.comparison import compare_predictions  # noqa: E402
from app.core import calculate_hepatic_clearance, make_input_from_species  # noqa: E402
from app.nca import ConcentrationTimePoint, NCAProfileInput, calculate_profile_nca  # noqa: E402


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "literature"


def _load_cases():
    with (FIXTURE_DIR / "ivive_nca_connection_cases.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


CONNECTION_CASES = _load_cases()


def _run_nca(profile: dict) -> dict:
    return calculate_profile_nca(
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


def _run_ivive(ivive_input: dict):
    return calculate_hepatic_clearance(
        make_input_from_species(
            species=ivive_input["species"],
            system=ivive_input["system"],
            clint=ivive_input["clint"],
            fu_inc=ivive_input["fu_inc"],
            fu_p=ivive_input["fu_p"],
            rbp=ivive_input["rbp"],
            model=ivive_input.get("model"),
            liver_blood_flow_L_per_h=ivive_input.get("liver_blood_flow_L_per_h"),
            liver_weight_g=ivive_input.get("liver_weight_g"),
            hpgl=ivive_input.get("hpgl"),
            mppgl=ivive_input.get("mppgl"),
        )
    )


def _comparison(observed_value: float, predicted_value: float, case: dict, observed_method: str):
    comparisons = compare_predictions(
        [
            {
                "compound_id": case["compound"],
                "species": "human",
                "parameter": "clearance",
                "unit": "L/h",
                "value": observed_value,
                "method": observed_method,
            }
        ],
        [
            {
                "compound_id": case["compound"],
                "species": "human",
                "parameter": "clearance",
                "unit": "L/h",
                "value": predicted_value,
                "method": "ivive_well_stirred",
            }
        ],
    )
    assert len(comparisons) == 1
    return comparisons[0]


@pytest.mark.parametrize("case", CONNECTION_CASES, ids=lambda item: item["case_id"])
def test_raw_nca_matches_literature_reported_clearance(case):
    nca_result = _run_nca(case["profile"])
    expected = case["reported_outputs"]
    tolerance = case["tolerances"]["nca_reported_relative"]

    assert nca_result["clearance_label"] == "CL"
    assert nca_result["clearance"] == pytest.approx(expected["clearance"], rel=tolerance), (
        f"{case['case_id']} NCA clearance mismatch. "
        f"calculated={nca_result['clearance']:.8g}, reported={expected['clearance']:.8g}. "
        f"Source: {case['source']}"
    )
    assert nca_result["aucinf_obs"] == pytest.approx(expected["aucinf_obs"], rel=tolerance), (
        f"{case['case_id']} NCA AUCinf mismatch. "
        f"calculated={nca_result['aucinf_obs']:.8g}, reported={expected['aucinf_obs']:.8g}. "
        f"Source: {case['source']}"
    )
    assert nca_result["lambda_z"] == pytest.approx(expected["lambda_z"], rel=tolerance)
    assert nca_result["half_life"] == pytest.approx(expected["half_life"], rel=tolerance)


@pytest.mark.parametrize("case", CONNECTION_CASES, ids=lambda item: item["case_id"])
def test_ivive_predictions_compare_to_nca_and_literature_clearance(case):
    nca_result = _run_nca(case["profile"])
    reported_clearance = case["reported_outputs"]["clearance"]
    max_fold_error = case["tolerances"]["ivive_max_fold_error"]

    for ivive_input in case["ivive_inputs"]:
        ivive_result = _run_ivive(ivive_input)
        predicted_clearance = ivive_result.hepatic_plasma_clearance_L_per_h
        nca_comparison = _comparison(
            nca_result["clearance"],
            predicted_clearance,
            case,
            observed_method="nca_from_raw_profile",
        )
        literature_comparison = _comparison(
            reported_clearance,
            predicted_clearance,
            case,
            observed_method="literature_reported_clearance",
        )

        expected_class = ivive_input["expected_predictive_class"]
        if expected_class == "good":
            assert nca_comparison["fold_error"] <= max_fold_error, (
                f"{case['case_id']} {ivive_input['case_label']} was not within {max_fold_error}-fold "
                f"of NCA clearance. predicted={predicted_clearance:.8g} L/h, "
                f"observed={nca_result['clearance']:.8g} L/h, "
                f"fold_error={nca_comparison['fold_error']:.4g}. Source: {case['source']}"
            )
            assert literature_comparison["fold_error"] <= max_fold_error, (
                f"{case['case_id']} {ivive_input['case_label']} was not within {max_fold_error}-fold "
                f"of reported literature clearance. predicted={predicted_clearance:.8g} L/h, "
                f"reported={reported_clearance:.8g} L/h, "
                f"fold_error={literature_comparison['fold_error']:.4g}. Source: {case['source']}"
            )
        elif expected_class == "poor":
            assert nca_comparison["fold_error"] > max_fold_error, (
                f"{case['case_id']} {ivive_input['case_label']} was expected to be outside "
                f"{max_fold_error}-fold but was fold_error={nca_comparison['fold_error']:.4g}. "
                f"predicted={predicted_clearance:.8g} L/h, observed={nca_result['clearance']:.8g} L/h. "
                f"Source: {case['source']}"
            )
        else:
            raise AssertionError(f"Unknown expected_predictive_class: {expected_class}")


def test_hepatocyte_case_is_better_than_microsome_for_rosuvastatin():
    case = next(item for item in CONNECTION_CASES if item["role"] == "hepatocyte_good_microsome_poor_case")
    nca_result = _run_nca(case["profile"])
    fold_errors = {}

    for ivive_input in case["ivive_inputs"]:
        ivive_result = _run_ivive(ivive_input)
        comparison = _comparison(
            nca_result["clearance"],
            ivive_result.hepatic_plasma_clearance_L_per_h,
            case,
            observed_method="nca_from_raw_profile",
        )
        fold_errors[ivive_input["system"]] = comparison["fold_error"]

    assert fold_errors["hepatocyte"] < fold_errors["microsome"], (
        f"{case['case_id']} should show hepatocyte IVIVE better than microsome IVIVE. "
        f"hepatocyte_fold_error={fold_errors['hepatocyte']:.4g}, "
        f"microsome_fold_error={fold_errors['microsome']:.4g}. Source: {case['source']}"
    )
    assert fold_errors["hepatocyte"] <= case["tolerances"]["ivive_max_fold_error"]
    assert fold_errors["microsome"] > case["tolerances"]["ivive_max_fold_error"]
