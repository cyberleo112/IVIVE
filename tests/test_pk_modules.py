from __future__ import annotations

import math
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.allometry import AllometryInput, AllometrySpeciesInput, scale_allometry  # noqa: E402
from app.main import app  # noqa: E402
from app.nca import (  # noqa: E402
    ConcentrationTimePoint,
    NCAProfileInput,
    auc_linear_up_log_down,
    calculate_profile_nca,
)


def _point(time, concentration):
    return ConcentrationTimePoint(time=float(time), concentration=float(concentration))


def test_linear_up_log_down_auc_uses_linear_up_and_log_down():
    points = [_point(0, 0), _point(1, 10), _point(2, 8)]
    expected = 5.0 + ((10.0 - 8.0) / math.log(10.0 / 8.0))
    assert auc_linear_up_log_down(points) == pytest.approx(expected)


def test_nca_profile_calculates_terminal_phase_and_route_aware_apparent_values():
    profile = NCAProfileInput(
        compound_id="cmpd-1",
        study_id="study-1",
        subject_id="subj-1",
        species="human",
        matrix="plasma",
        route="extravascular",
        dose=100.0,
        dose_unit="mg",
        time_unit="h",
        concentration_unit="mg/L",
        observations=[
            _point(0, 0),
            _point(1, 10),
            _point(2, 8),
            _point(4, 4),
            _point(6, 2),
        ],
    )
    result = calculate_profile_nca(profile)

    assert result["cmax"] == pytest.approx(10.0)
    assert result["tmax"] == pytest.approx(1.0)
    assert result["lambda_z"] == pytest.approx(math.log(2.0) / 2.0)
    assert result["kel"] == pytest.approx(result["lambda_z"])
    assert result["half_life"] == pytest.approx(2.0)
    assert result["lambda_z_points"] == [2.0, 4.0, 6.0]
    assert result["aucinf_obs"] == pytest.approx(result["auclast"] + 2.0 / result["lambda_z"])
    assert result["clearance_label"] == "CL/F"
    assert result["volume_z_label"] == "Vz/F"
    assert result["clearance"] == pytest.approx(100.0 / result["aucinf_obs"])
    assert result["volume_z"] == pytest.approx(result["clearance"] / result["lambda_z"])
    assert result["volume_ss"] is None
    assert "vss_not_calculated_for_extravascular" in result["warnings"]


def test_nca_tied_cmax_uses_first_tmax_and_iv_labels():
    profile = NCAProfileInput(
        compound_id=None,
        study_id=None,
        subject_id=None,
        species=None,
        matrix="blood",
        route="iv_bolus",
        dose=10.0,
        dose_unit="mg",
        time_unit="h",
        concentration_unit="mg/L",
        observations=[
            _point(0, 10),
            _point(1, 10),
            _point(2, 5),
            _point(4, 2.5),
            _point(6, 1.25),
        ],
    )
    result = calculate_profile_nca(profile)
    assert result["tmax"] == pytest.approx(0.0)
    assert result["clearance_label"] == "CL"
    assert result["volume_z_label"] == "Vz"


def test_nca_iv_bolus_calculates_mrt_and_vss_from_aumc():
    profile = NCAProfileInput(
        compound_id=None,
        study_id=None,
        subject_id=None,
        species=None,
        matrix="plasma",
        route="iv_bolus",
        dose=10.0,
        dose_unit="mg",
        time_unit="h",
        concentration_unit="mg/L",
        observations=[
            _point(0, 10),
            _point(1, 5),
            _point(2, 2.5),
            _point(3, 1.25),
        ],
        terminal_times=[1, 2, 3],
    )
    result = calculate_profile_nca(profile)
    lambda_z = math.log(2.0)

    assert result["lambda_z"] == pytest.approx(lambda_z)
    assert result["aucinf_obs"] == pytest.approx(10.0 / lambda_z)
    assert result["aumcinf_obs"] == pytest.approx(10.0 / (lambda_z ** 2))
    assert result["mrtinf_obs"] == pytest.approx(1.0 / lambda_z)
    assert result["volume_ss"] == pytest.approx(result["clearance"] * result["mrtinf_obs"])
    assert result["volume_ss"] == pytest.approx(1.0)
    assert result["volume_ss_label"] == "Vss"


def test_nca_flags_missing_terminal_phase_without_failing_core_exposure():
    profile = NCAProfileInput(
        compound_id=None,
        study_id=None,
        subject_id=None,
        species=None,
        matrix="serum",
        route="extravascular",
        dose=5.0,
        dose_unit="mg",
        time_unit="h",
        concentration_unit="ng/mL",
        observations=[_point(0, 0), _point(1, 4), _point(2, 3)],
    )
    result = calculate_profile_nca(profile)
    assert result["auclast"] > 0
    assert result["lambda_z"] is None
    assert "lambda_z_not_estimable" in result["warnings"]


def test_nca_rejects_invalid_missing_dose():
    profile = NCAProfileInput(
        compound_id=None,
        study_id=None,
        subject_id=None,
        species=None,
        matrix="plasma",
        route="extravascular",
        dose=0.0,
        dose_unit="mg",
        time_unit="h",
        concentration_unit="ng/mL",
        observations=[_point(0, 0), _point(1, 1)],
    )
    with pytest.raises(ValueError, match="dose"):
        calculate_profile_nca(profile)


def test_multi_species_allometry_log_log_fit():
    rows = [
        AllometrySpeciesInput("small", 1.0, "clearance", 2.0 * (1.0 ** 0.75), "L/h"),
        AllometrySpeciesInput("medium", 4.0, "clearance", 2.0 * (4.0 ** 0.75), "L/h"),
        AllometrySpeciesInput("large", 16.0, "clearance", 2.0 * (16.0 ** 0.75), "L/h"),
    ]
    result = scale_allometry(AllometryInput(rows=rows, target_body_weight_kg=64.0))
    assert result["method"] == "multi_species_log_log_allometry"
    assert result["coefficient"] == pytest.approx(2.0)
    assert result["exponent"] == pytest.approx(0.75)
    assert result["r_squared"] == pytest.approx(1.0)
    assert result["predicted_value"] == pytest.approx(2.0 * (64.0 ** 0.75))


def test_single_species_allometry_is_flagged_exploratory():
    rows = [AllometrySpeciesInput("rat", 0.25, "volume", 0.2, "L")]
    result = scale_allometry(AllometryInput(rows=rows, target_body_weight_kg=70.0))
    assert result["method"] == "single_species_fixed_exponent"
    assert result["exponent"] == pytest.approx(1.0)
    assert "single_species_exploratory" in result["flags"]
    assert result["predicted_value"] == pytest.approx(56.0)


def test_allometry_rejects_invalid_inputs():
    rows = [AllometrySpeciesInput("rat", 0.25, "half_life", 2.0, "h")]
    with pytest.raises(ValueError, match="parameter"):
        scale_allometry(AllometryInput(rows=rows))


def test_nca_api_accepts_multiple_profiles():
    client = TestClient(app)
    payload = {
        "profiles": [
            {
                "compound_id": "cmpd-1",
                "matrix": "plasma",
                "route": "extravascular",
                "dose": 100,
                "dose_unit": "mg",
                "time_unit": "h",
                "concentration_unit": "mg/L",
                "observations": [
                    {"time": 0, "concentration": 0},
                    {"time": 1, "concentration": 10},
                    {"time": 2, "concentration": 8},
                    {"time": 4, "concentration": 4},
                    {"time": 6, "concentration": 2},
                ],
            },
            {
                "compound_id": "cmpd-2",
                "matrix": "blood",
                "route": "iv_bolus",
                "dose": 10,
                "observations": [
                    {"time": 0, "concentration": 10},
                    {"time": 1, "concentration": 5},
                    {"time": 2, "concentration": 2.5},
                    {"time": 3, "concentration": 1.25},
                ],
            },
        ]
    }
    response = client.post("/api/nca/plasma", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["total_profiles"] == 2
    assert body["profiles"][0]["clearance_label"] == "CL/F"
    assert body["profiles"][1]["clearance_label"] == "CL"


def test_allometry_api_is_independent_from_nca():
    client = TestClient(app)
    response = client.post("/api/allometry/scale", json={
        "rows": [
            {"species": "rat", "body_weight_kg": 0.25, "parameter": "clearance", "value": 0.1, "unit": "L/h"}
        ],
        "target_body_weight_kg": 70,
    })
    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "single_species_fixed_exponent"
    assert "single_species_exploratory" in body["flags"]


def test_prediction_compare_api_reports_fold_error():
    client = TestClient(app)
    response = client.post("/api/prediction/compare", json={
        "observed": [
            {"compound_id": "A", "species": "human", "parameter": "clearance", "value": 10, "unit": "L/h", "method": "NCA"}
        ],
        "predicted": [
            {"compound_id": "A", "species": "human", "parameter": "CL", "value": 25, "unit": "L/h", "method": "allometry"}
        ],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["total_comparisons"] == 1
    row = body["comparisons"][0]
    assert row["predicted_to_observed_ratio"] == pytest.approx(2.5)
    assert row["fold_error"] == pytest.approx(2.5)
    assert not row["within_2_fold"]
    assert row["within_3_fold"]
