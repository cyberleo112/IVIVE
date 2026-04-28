#!/usr/bin/env python3
"""Species IVIVE Hepatic Plasma Clearance Calculator (CLI).

Thin command-line wrapper. All math and species defaults live in `app/core.py`
so the CLI and the web app share a single source of truth.

Run examples:
    python "Hepatocyte and Microsomes Clearance IVIVE.py" --show-species
    python "Hepatocyte and Microsomes Clearance IVIVE.py" \\
        --species human --system hepatocyte \\
        --clint 6.4 --fu-inc 0.76 --fu-p 0.023 --rbp 0.667
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow running from the project root even when invoked from elsewhere.
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from app.core import (  # noqa: E402
    SPECIES_DEFAULTS,
    IVIVEInput,
    IVIVEResult,
    calculate_hepatic_clearance,
    make_input_from_species,
)


def print_species_table() -> None:
    print("\n=== Default Species Scaling Factors ===")
    print(
        f"{'Species':<8} {'Weight kg':>10} {'Gender / default':<24} "
        f"{'Qh L/h':>10} {'Liver g':>10} {'HPGL M/g':>12} {'MPPGL mg/g':>12}"
    )
    print("-" * 94)
    for item in SPECIES_DEFAULTS.values():
        print(
            f"{item.species:<8} {item.weight_kg:>10g} {item.gender_default:<24} "
            f"{item.liver_blood_flow_L_per_h:>10g} {item.liver_weight_g:>10g} "
            f"{item.hepatocytes_million_per_g_liver:>12g} "
            f"{item.microsomal_protein_mg_per_g_liver:>12g}"
        )


def print_result(result: IVIVEResult, inputs: IVIVEInput) -> None:
    unit = (
        "uL/min/million cells"
        if inputs.system == "hepatocyte"
        else "uL/min/mg microsomal protein"
    )
    print("\n=== IVIVE Hepatic Clearance Result ===")
    print(f"Species: {result.species}")
    print(f"System: {result.system}")
    print("\n--- Compound-dependent inputs ---")
    print(f"In vitro CLint: {inputs.clint_in_vitro:.6g} {unit}")
    print(f"fu_inc: {inputs.fu_inc:.6g}")
    print(f"fu_p: {inputs.fu_p:.6g}")
    print(f"Blood/plasma ratio Rbp: {inputs.blood_to_plasma_ratio:.6g}")
    print("\n--- Species-specific scaling factors used ---")
    print(f"Liver blood flow Qh: {inputs.liver_blood_flow_L_per_h:.6g} L/h")
    print(f"Liver weight: {inputs.liver_weight_g:.6g} g")
    print(f"Hepatocellularity: {inputs.hepatocytes_million_per_g_liver:.6g} million cells/g liver")
    print(f"Microsomal protein: {inputs.microsomal_protein_mg_per_g_liver:.6g} mg/g liver")
    print("\n--- Intermediate outputs ---")
    print(f"Unbound in vitro CLint: {result.clint_u_in_vitro:.6g} {unit}")
    print(f"Total scaling amount: {result.total_scaling_amount:,.6g} {result.scaling_unit}")
    print(f"Whole-liver unbound CLint: {result.clint_u_liver_L_per_h:.6g} L/h")
    print(f"Plasma liver flow, Rbp * Qh: {result.plasma_liver_flow_L_per_h:.6g} L/h")
    print("\n--- Final outputs ---")
    print(f"Predicted hepatic plasma clearance: {result.hepatic_plasma_clearance_L_per_h:.6g} L/h")
    print(f"Predicted hepatic plasma clearance: {result.hepatic_plasma_clearance_mL_per_min:.6g} mL/min")
    print(f"Plasma extraction ratio: {result.extraction_ratio_plasma:.6g}")
    print(
        f"Hepatic extraction ratio (Eh): {result.extraction_ratio_plasma * 100:.4g}% "
        f"-> {result.clearance_classification} clearance "
        f"(Low <30%, Moderate 30-70%, High >70%)"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Predict hepatic plasma clearance from hepatocyte or microsome in vitro CLint."
    )
    parser.add_argument("--system", default="hepatocyte", help="hepatocyte or microsome. Default: hepatocyte.")
    parser.add_argument("--species", default="human", help="Species: human, mouse, rat, dog, cyno/monkey. Default: human.")
    parser.add_argument("--clint", type=float, default=6.4, help="In vitro CLint. Units depend on system.")
    parser.add_argument("--fu-inc", type=float, default=0.76, help="Fraction unbound in incubation (0-1).")
    parser.add_argument("--fu-p", type=float, default=0.023, help="Fraction unbound in plasma (0-1).")
    parser.add_argument("--rbp", type=float, default=0.667, help="Blood-to-plasma concentration ratio.")
    parser.add_argument("--q-hepatic", type=float, default=None, help="Optional override for liver blood flow in L/h.")
    parser.add_argument("--liver-weight", type=float, default=None, help="Optional override for liver weight in g.")
    parser.add_argument("--hpgl", type=float, default=None, help="Optional override for hepatocytes million/g liver.")
    parser.add_argument("--mppgl", type=float, default=None, help="Optional override for microsomal protein mg/g liver.")
    parser.add_argument("--show-species", action="store_true", help="Show default species scaling factor table and exit.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.show_species:
        print_species_table()
        return

    ivive_input = make_input_from_species(
        species=args.species,
        system=args.system,
        clint=args.clint,
        fu_inc=args.fu_inc,
        fu_p=args.fu_p,
        rbp=args.rbp,
        liver_blood_flow_L_per_h=args.q_hepatic,
        liver_weight_g=args.liver_weight,
        hpgl=args.hpgl,
        mppgl=args.mppgl,
    )
    result = calculate_hepatic_clearance(ivive_input)
    print_result(result, ivive_input)


if __name__ == "__main__":
    main()
