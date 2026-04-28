"""Pytest harness for the 11 built-in IVIVE validation cases."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.validation import VALIDATION_CASES, run_case  # noqa: E402


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
