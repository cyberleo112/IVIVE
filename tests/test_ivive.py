"""Pytest harness for the 11 built-in IVIVE validation cases."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.validation import VALIDATION_CASES, run_case  # noqa: E402
from app.batch import process_rows  # noqa: E402
from app.core import get_species_defaults, make_input_from_species  # noqa: E402


@pytest.mark.parametrize("case", VALIDATION_CASES, ids=lambda c: c.case_id)
def test_validation_case_passes(case):
    out = run_case(case)
    assert out["pass"], (
        f"{case.case_id} failed: "
        f"CLp predicted={out['predicted_clp_L_per_h']:.6g} L/h "
        f"vs expected={out['expected_clp_L_per_h']:.6g} "
        f"(rel err={out['clp_relative_error_percent']:.3f}%); "
        f"Eh predicted={out['predicted_eh_percent']:.6g}% "
        f"vs expected={out['expected_eh_percent']:.6g}% "
        f"(abs err={out['eh_absolute_error_pp']:.3f} pp)"
    )


def test_run_all_summary_complete():
    from app.validation import run_all
    payload = run_all()
    assert payload["total"] == 11
    assert payload["passed"] + payload["failed"] == payload["total"]


def test_gastroplus_defaults_remain_default():
    defaults = get_species_defaults("human")
    assert defaults.liver_blood_flow_L_per_h == pytest.approx(84.42)
    assert defaults.liver_weight_g == pytest.approx(1639)
    assert defaults.hepatocytes_million_per_g_liver == pytest.approx(120)
    assert defaults.microsomal_protein_mg_per_g_liver == pytest.approx(38)


def test_simcyp_defaults_are_available():
    defaults = get_species_defaults("human", "simcyp")
    assert defaults.liver_blood_flow_L_per_h == pytest.approx(91.8)
    assert defaults.liver_weight_g == pytest.approx(1782.648)
    assert defaults.hepatocytes_million_per_g_liver == pytest.approx(117.52)
    assert defaults.microsomal_protein_mg_per_g_liver == pytest.approx(39.791)


def test_model_specific_input_uses_selected_defaults():
    ivive_input = make_input_from_species(
        species="mouse",
        system="hepatocyte",
        clint=1,
        fu_inc=1,
        fu_p=1,
        rbp=1,
        model="simcyp",
    )
    assert ivive_input.model == "simcyp"
    assert ivive_input.model_label == "Simcyp"
    assert ivive_input.liver_blood_flow_L_per_h == pytest.approx(0.189216)
    assert ivive_input.liver_weight_g == pytest.approx(1.2852)
    assert ivive_input.hepatocytes_million_per_g_liver == pytest.approx(135)


def test_batch_both_expands_to_two_model_results():
    rows = [{
        "compound_id": "Compound 1",
        "model": "Both",
        "species": "human",
        "system": "hepatocyte",
        "clint_in_vitro": 6.4,
        "fu_inc": 0.76,
        "fu_p": 0.023,
        "rbp": 0.667,
    }]
    out = process_rows(rows)
    assert [r["model"] for r in out] == ["gastroplus", "simcyp"]
    assert all(r["status"] == "ok" for r in out)
