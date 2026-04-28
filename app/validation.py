"""Built-in validation cases sourced from `IVIVE validation.md`.

Runs the canonical 11 cases (6 hepatocyte + 5 microsome) against the IVIVE math
and reports pass/fail using a configurable tolerance.

Tolerances:
  - CLp: relative tolerance, default 2%
  - Eh:  absolute tolerance in percentage points, default 0.5 pp

These are looser than typical numerical tolerances because the expected values
in `IVIVE validation.md` are rounded to 2-4 significant figures.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from app.core import calculate_hepatic_clearance, make_input_from_species


@dataclass(frozen=True)
class ValidationCase:
    case_id: str
    compound: str
    species: str
    system: str
    clint: float
    fu_inc: float
    fu_p: float
    rbp: float
    expected_clp_L_per_h: float
    expected_eh_percent: float


# Sourced verbatim from `IVIVE validation.md`.
VALIDATION_CASES: List[ValidationCase] = [
    # --- Hepatocyte (6 cases) ---
    ValidationCase("HEP-1", "Compound 1", "human", "hepatocyte",
                   clint=6.4,  fu_inc=0.76,  fu_p=0.023,    rbp=0.667,
                   expected_clp_L_per_h=2.196,   expected_eh_percent=3.9),
    ValidationCase("HEP-2", "Compound 1", "mouse", "hepatocyte",
                   clint=20.0, fu_inc=0.80,  fu_p=0.05469,  rbp=0.7985,
                   expected_clp_L_per_h=0.012,   expected_eh_percent=14.7),
    ValidationCase("HEP-3", "Compound 1", "rat",   "hepatocyte",
                   clint=2.2,  fu_inc=0.92,  fu_p=0.0238,   rbp=1.074,
                   expected_clp_L_per_h=0.0045,  expected_eh_percent=0.59),
    ValidationCase("HEP-4", "Compound 1", "dog",   "hepatocyte",
                   clint=3.2,  fu_inc=0.84,  fu_p=0.0346,   rbp=0.7147,
                   expected_clp_L_per_h=0.302,   expected_eh_percent=2.28),
    ValidationCase("HEP-5", "Compound 1", "cyno",  "hepatocyte",
                   clint=5.0,  fu_inc=1.00,  fu_p=0.0075,   rbp=0.7147,
                   expected_clp_L_per_h=0.0269,  expected_eh_percent=0.432),
    ValidationCase("HEP-6", "Compound 2", "human", "hepatocyte",
                   clint=100.0, fu_inc=0.32, fu_p=0.10,     rbp=0.5,
                   expected_clp_L_per_h=37.87,   expected_eh_percent=89.7),

    # --- Microsome (5 cases) ---
    ValidationCase("MIC-1", "Microsome A", "mouse", "microsome",
                   clint=20.0, fu_inc=0.1835, fu_p=0.02493, rbp=1.0,
                   expected_clp_L_per_h=0.008,   expected_eh_percent=7.87),
    ValidationCase("MIC-2", "Microsome A", "rat",   "microsome",
                   clint=20.0, fu_inc=0.1835, fu_p=0.02493, rbp=1.0,
                   expected_clp_L_per_h=0.062,   expected_eh_percent=8.76),
    ValidationCase("MIC-3", "Microsome B", "human", "microsome",
                   clint=19.0, fu_inc=0.35,  fu_p=0.11,     rbp=0.2,
                   expected_clp_L_per_h=9.61,    expected_eh_percent=56.9),
    ValidationCase("MIC-4", "Microsome C", "cyno",  "microsome",
                   clint=19.0, fu_inc=0.05551, fu_p=0.01536, rbp=0.7147,
                   expected_clp_L_per_h=1.0,     expected_eh_percent=16.16),
    ValidationCase("MIC-5", "Microsome D", "dog",   "microsome",
                   clint=7.8,  fu_inc=0.2545, fu_p=0.02802, rbp=0.7147,
                   expected_clp_L_per_h=0.946,   expected_eh_percent=7.15),
]


# Default tolerances; loose enough to absorb rounding in the source doc.
DEFAULT_CLP_RELATIVE_TOL_PCT = 2.0
DEFAULT_EH_ABSOLUTE_TOL_PP = 0.5


def run_case(case: ValidationCase) -> Dict[str, Any]:
    """Run a single validation case and return a dict for the API response."""
    ivive_input = make_input_from_species(
        species=case.species,
        system=case.system,
        clint=case.clint,
        fu_inc=case.fu_inc,
        fu_p=case.fu_p,
        rbp=case.rbp,
    )
    result = calculate_hepatic_clearance(ivive_input)
    predicted_clp = result.hepatic_plasma_clearance_L_per_h
    predicted_eh_pct = result.extraction_ratio_plasma * 100.0

    if case.expected_clp_L_per_h == 0:
        clp_rel_err_pct = 0.0 if predicted_clp == 0 else float("inf")
    else:
        clp_rel_err_pct = (
            abs(predicted_clp - case.expected_clp_L_per_h)
            / case.expected_clp_L_per_h
            * 100.0
        )
    eh_abs_err_pp = abs(predicted_eh_pct - case.expected_eh_percent)

    passed = (
        clp_rel_err_pct <= DEFAULT_CLP_RELATIVE_TOL_PCT
        and eh_abs_err_pp <= DEFAULT_EH_ABSOLUTE_TOL_PP
    )

    return {
        "case_id": case.case_id,
        "compound": case.compound,
        "species": ivive_input.species,
        "system": ivive_input.system,
        "expected_clp_L_per_h": case.expected_clp_L_per_h,
        "expected_eh_percent": case.expected_eh_percent,
        "predicted_clp_L_per_h": predicted_clp,
        "predicted_eh_percent": predicted_eh_pct,
        "clp_relative_error_percent": clp_rel_err_pct,
        "eh_absolute_error_pp": eh_abs_err_pp,
        "pass": passed,
    }


def run_all() -> Dict[str, Any]:
    """Run all 11 validation cases and return a summary payload."""
    cases = [run_case(c) for c in VALIDATION_CASES]
    passed = sum(1 for c in cases if c["pass"])
    return {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "clp_relative_tolerance_percent": DEFAULT_CLP_RELATIVE_TOL_PCT,
        "eh_absolute_tolerance_pp": DEFAULT_EH_ABSOLUTE_TOL_PP,
        "cases": cases,
    }
