"""Excel/CSV template generation and batch parsing/exporting.

Template layout:
- Sheet "Inputs": one row per compound; columns include required and optional
  override fields. The first two rows are pre-filled examples.
- Sheet "Instructions": units, accepted aliases, and notes.
"""

import csv
import io
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.core import (
    SPECIES_DEFAULTS,
    SPECIES_DISPLAY,
    calculate_hepatic_clearance,
    make_input_from_species,
    normalize_species,
)


INPUT_COLUMNS: List[Tuple[str, str]] = [
    ("compound_id", "Free-text label for the compound (optional)."),
    ("species", "Pick from dropdown: human | mouse | rat | dog | monkey."),
    ("system", "Pick from dropdown: hepatocyte | microsome."),
    ("clint_in_vitro", "In vitro CLint. Units: uL/min/million cells (hepatocyte) OR uL/min/mg microsomal protein (microsome). Must be > 0."),
    ("fu_inc", "Fraction unbound in incubation. Range: 0 < fu_inc <= 1 (e.g. 0.76)."),
    ("fu_p", "Fraction unbound in plasma. Range: 0 < fu_p <= 1 (e.g. 0.023)."),
    ("rbp", "Blood-to-plasma concentration ratio (>0, e.g. 0.667)."),
    ("liver_blood_flow_L_per_h", "Optional override for Qh (L/h)."),
    ("liver_weight_g", "Optional override for liver weight (g)."),
    ("hpgl", "Optional override for hepatocytes (million cells / g liver)."),
    ("mppgl", "Optional override for microsomal protein (mg / g liver)."),
]

# Pretty header text shown in the Inputs sheet (units / range hints).
HEADER_DISPLAY: Dict[str, str] = {
    "compound_id": "compound_id",
    "species": "species (dropdown)",
    "system": "system (dropdown)",
    "clint_in_vitro": "clint_in_vitro (uL/min/million cells [hep] or uL/min/mg [mic])",
    "fu_inc": "fu_inc (0 < value <= 1)",
    "fu_p": "fu_p (0 < value <= 1)",
    "rbp": "rbp (blood/plasma, > 0)",
    "liver_blood_flow_L_per_h": "liver_blood_flow_L_per_h (L/h, optional)",
    "liver_weight_g": "liver_weight_g (g, optional)",
    "hpgl": "hpgl (million cells / g liver, optional)",
    "mppgl": "mppgl (mg / g liver, optional)",
}

# Allowed values for the species/system dropdowns in the template.
SPECIES_DROPDOWN_VALUES: List[str] = ["human", "mouse", "rat", "dog", "monkey"]
SYSTEM_DROPDOWN_VALUES: List[str] = ["hepatocyte", "microsome"]

OUTPUT_COLUMNS: List[str] = [
    "clp_L_per_h",
    "clp_mL_per_min",
    "eh_percent",
    "clearance_classification",
    "status",
    "error_message",
]

EXAMPLE_ROWS: List[Dict[str, Any]] = [
    {
        "compound_id": "Compound 1",
        "species": "human",
        "system": "hepatocyte",
        "clint_in_vitro": 6.4,
        "fu_inc": 0.76,
        "fu_p": 0.023,
        "rbp": 0.667,
    },
    {
        "compound_id": "Compound 2",
        "species": "human",
        "system": "microsome",
        "clint_in_vitro": 19.0,
        "fu_inc": 0.35,
        "fu_p": 0.11,
        "rbp": 0.2,
    },
]


def _autosize(ws) -> None:
    for col_idx, col in enumerate(ws.columns, start=1):
        max_len = 0
        for cell in col:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 40)


def build_template_workbook() -> bytes:
    """Build the input-template .xlsx and return its bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Inputs"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2563EB")

    column_keys = [c[0] for c in INPUT_COLUMNS]
    headers = [HEADER_DISPLAY.get(k, k) for k in column_keys]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[1].height = 32

    for row in EXAMPLE_ROWS:
        ws.append([row.get(col, None) for col in column_keys])

    _autosize(ws)
    ws.freeze_panes = "A2"

    species_col_idx = column_keys.index("species") + 1
    system_col_idx = column_keys.index("system") + 1
    species_letter = get_column_letter(species_col_idx)
    system_letter = get_column_letter(system_col_idx)

    species_values = ",".join(SPECIES_DROPDOWN_VALUES)
    system_values = ",".join(SYSTEM_DROPDOWN_VALUES)

    species_dv = DataValidation(
        type="list",
        formula1=f'"{species_values}"',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid species",
        error="Pick one of: " + ", ".join(SPECIES_DROPDOWN_VALUES),
        promptTitle="Species",
        prompt="Choose: " + ", ".join(SPECIES_DROPDOWN_VALUES),
    )
    species_dv.showInputMessage = True
    species_dv.add(f"{species_letter}2:{species_letter}1048576")
    ws.add_data_validation(species_dv)

    system_dv = DataValidation(
        type="list",
        formula1=f'"{system_values}"',
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="Invalid system",
        error="Pick one of: " + ", ".join(SYSTEM_DROPDOWN_VALUES),
        promptTitle="In vitro system",
        prompt="Choose: " + ", ".join(SYSTEM_DROPDOWN_VALUES),
    )
    system_dv.showInputMessage = True
    system_dv.add(f"{system_letter}2:{system_letter}1048576")
    ws.add_data_validation(system_dv)

    fu_inc_letter = get_column_letter(column_keys.index("fu_inc") + 1)
    fu_p_letter = get_column_letter(column_keys.index("fu_p") + 1)
    fu_inc_dv = DataValidation(
        type="decimal",
        operator="between",
        formula1=0,
        formula2=1,
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="fu_inc out of range",
        error="fu_inc must be a fraction between 0 and 1.",
        promptTitle="fu_inc",
        prompt="Fraction unbound in incubation (0 < value <= 1).",
    )
    fu_inc_dv.showInputMessage = True
    fu_inc_dv.add(f"{fu_inc_letter}2:{fu_inc_letter}1048576")
    ws.add_data_validation(fu_inc_dv)

    fu_p_dv = DataValidation(
        type="decimal",
        operator="between",
        formula1=0,
        formula2=1,
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="fu_p out of range",
        error="fu_p must be a fraction between 0 and 1.",
        promptTitle="fu_p",
        prompt="Fraction unbound in plasma (0 < value <= 1).",
    )
    fu_p_dv.showInputMessage = True
    fu_p_dv.add(f"{fu_p_letter}2:{fu_p_letter}1048576")
    ws.add_data_validation(fu_p_dv)

    clint_letter = get_column_letter(column_keys.index("clint_in_vitro") + 1)
    clint_dv = DataValidation(
        type="decimal",
        operator="greaterThanOrEqual",
        formula1=0,
        allow_blank=True,
        showErrorMessage=True,
        errorTitle="CLint out of range",
        error="CLint must be >= 0.",
        promptTitle="CLint (in vitro)",
        prompt="uL/min/million cells (hepatocyte) or uL/min/mg microsomal protein (microsome).",
    )
    clint_dv.showInputMessage = True
    clint_dv.add(f"{clint_letter}2:{clint_letter}1048576")
    ws.add_data_validation(clint_dv)

    instr = wb.create_sheet("Instructions")
    instr["A1"] = "IVIVE batch input template"
    instr["A1"].font = Font(bold=True, size=14)
    instr["A3"] = "Column"
    instr["B3"] = "Description"
    for cell in instr[3]:
        cell.font = Font(bold=True)

    for i, (col, desc) in enumerate(INPUT_COLUMNS, start=4):
        instr.cell(row=i, column=1, value=col)
        instr.cell(row=i, column=2, value=desc)

    next_row = 4 + len(INPUT_COLUMNS) + 2
    instr.cell(row=next_row, column=1, value="Species defaults used when not overridden:").font = Font(bold=True)
    next_row += 1
    instr.cell(row=next_row, column=1, value="species").font = Font(bold=True)
    instr.cell(row=next_row, column=2, value="Qh (L/h)").font = Font(bold=True)
    instr.cell(row=next_row, column=3, value="Liver weight (g)").font = Font(bold=True)
    instr.cell(row=next_row, column=4, value="HPGL (M/g)").font = Font(bold=True)
    instr.cell(row=next_row, column=5, value="MPPGL (mg/g)").font = Font(bold=True)
    for sf in SPECIES_DEFAULTS.values():
        next_row += 1
        instr.cell(row=next_row, column=1, value=sf.species)
        instr.cell(row=next_row, column=2, value=sf.liver_blood_flow_L_per_h)
        instr.cell(row=next_row, column=3, value=sf.liver_weight_g)
        instr.cell(row=next_row, column=4, value=sf.hepatocytes_million_per_g_liver)
        instr.cell(row=next_row, column=5, value=sf.microsomal_protein_mg_per_g_liver)

    next_row += 2
    instr.cell(row=next_row, column=1, value=(
        "Notes: 'monkey', 'cynomolgus', and 'cyno' all map to Cyno. "
        "'hep' is accepted for hepatocyte; 'mlm', 'rlm', 'hmm' are accepted for microsome. "
        "Leave any optional override blank to use the species default."
    )).alignment = Alignment(wrap_text=True)
    instr.column_dimensions["A"].width = 28
    instr.column_dimensions["B"].width = 60
    for c in ("C", "D", "E"):
        instr.column_dimensions[c].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    return float(s)


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _canonicalize_header(raw: Any) -> Optional[str]:
    """Map a header cell (which may include unit/range hints) to a canonical key.

    Examples:
      'fu_inc (0 < value <= 1)' -> 'fu_inc'
      'species (dropdown)'      -> 'species'
      'clint_in_vitro'          -> 'clint_in_vitro'
    Unknown headers return None.
    """
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    valid_keys = {c[0] for c in INPUT_COLUMNS}
    if text in valid_keys:
        return text
    # Take the leading token before any whitespace or '(' as a canonical key.
    head = text.split("(", 1)[0].strip().split()[0] if text else ""
    if head in valid_keys:
        return head
    return None


def parse_uploaded_file(filename: str, content: bytes) -> List[Dict[str, Any]]:
    """Parse an uploaded .xlsx or .csv file into a list of row dicts.

    Each row dict contains the canonical column keys from `INPUT_COLUMNS`.
    Headers may include unit/range hints in parentheses (matching the template).
    Unknown columns are ignored. Empty rows are skipped.
    """
    name = (filename or "").lower()
    rows: List[Dict[str, Any]] = []

    if name.endswith(".csv"):
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for raw in reader:
            row: Dict[str, Any] = {}
            for k, v in raw.items():
                key = _canonicalize_header(k)
                if key is not None:
                    row[key] = v
            if any((v is not None and str(v).strip() != "") for v in row.values()):
                rows.append(row)
        return rows

    if not (name.endswith(".xlsx") or name.endswith(".xlsm")):
        raise ValueError("Unsupported file type. Upload .xlsx or .csv.")

    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    if "Inputs" in wb.sheetnames:
        ws = wb["Inputs"]
    else:
        ws = wb.worksheets[0]

    iterator = ws.iter_rows(values_only=True)
    try:
        header = next(iterator)
    except StopIteration:
        return []
    header_keys = [_canonicalize_header(h) for h in header]

    for raw in iterator:
        if raw is None or all(v is None or str(v).strip() == "" for v in raw):
            continue
        row = {}
        for key, val in zip(header_keys, raw):
            if key is not None:
                row[key] = val
        if row:
            rows.append(row)
    return rows


def process_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run IVIVE on each parsed row; return per-row results with status."""
    results: List[Dict[str, Any]] = []
    for i, row in enumerate(rows, start=1):
        compound_id = _coerce_str(row.get("compound_id"))
        species_raw = _coerce_str(row.get("species"))
        system_raw = _coerce_str(row.get("system"))
        try:
            if not species_raw or not system_raw:
                raise ValueError("species and system are required.")
            ivive_input = make_input_from_species(
                species=species_raw,
                system=system_raw,
                clint=_coerce_float(row.get("clint_in_vitro")) or 0.0,
                fu_inc=_coerce_float(row.get("fu_inc")) or 0.0,
                fu_p=_coerce_float(row.get("fu_p")) or 0.0,
                rbp=_coerce_float(row.get("rbp")) or 0.0,
                liver_blood_flow_L_per_h=_coerce_float(row.get("liver_blood_flow_L_per_h")),
                liver_weight_g=_coerce_float(row.get("liver_weight_g")),
                hpgl=_coerce_float(row.get("hpgl")),
                mppgl=_coerce_float(row.get("mppgl")),
            )
            result = calculate_hepatic_clearance(ivive_input)
            results.append({
                "row": i,
                "compound_id": compound_id,
                "species": ivive_input.species,
                "system": ivive_input.system,
                "status": "ok",
                "error_message": None,
                "result": {
                    "compound_id": compound_id,
                    "species": ivive_input.species,
                    "species_key": normalize_species(species_raw),
                    "system": ivive_input.system,
                    "inputs_used": {
                        "clint_in_vitro": ivive_input.clint_in_vitro,
                        "fu_inc": ivive_input.fu_inc,
                        "fu_p": ivive_input.fu_p,
                        "rbp": ivive_input.blood_to_plasma_ratio,
                        "liver_blood_flow_L_per_h": ivive_input.liver_blood_flow_L_per_h,
                        "liver_weight_g": ivive_input.liver_weight_g,
                        "hpgl": ivive_input.hepatocytes_million_per_g_liver,
                        "mppgl": ivive_input.microsomal_protein_mg_per_g_liver,
                    },
                    "clint_u_in_vitro": result.clint_u_in_vitro,
                    "total_scaling_amount": result.total_scaling_amount,
                    "scaling_unit": result.scaling_unit,
                    "clint_u_liver_L_per_h": result.clint_u_liver_L_per_h,
                    "plasma_liver_flow_L_per_h": result.plasma_liver_flow_L_per_h,
                    "hepatic_plasma_clearance_L_per_h": result.hepatic_plasma_clearance_L_per_h,
                    "hepatic_plasma_clearance_mL_per_min": result.hepatic_plasma_clearance_mL_per_min,
                    "extraction_ratio_plasma": result.extraction_ratio_plasma,
                    "extraction_ratio_percent": result.extraction_ratio_plasma * 100.0,
                    "clearance_classification": result.clearance_classification,
                },
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "row": i,
                "compound_id": compound_id,
                "species": species_raw,
                "system": system_raw,
                "status": "error",
                "error_message": str(exc),
                "result": None,
            })
    return results


def _row_for_export(row: Dict[str, Any]) -> List[Any]:
    """Flatten one batch row result into the export column order."""
    res = row.get("result") or {}
    inp = (res.get("inputs_used") or {}) if isinstance(res, dict) else {}
    return [
        row.get("compound_id"),
        row.get("species"),
        row.get("system"),
        inp.get("clint_in_vitro"),
        inp.get("fu_inc"),
        inp.get("fu_p"),
        inp.get("rbp"),
        inp.get("liver_blood_flow_L_per_h"),
        inp.get("liver_weight_g"),
        inp.get("hpgl"),
        inp.get("mppgl"),
        res.get("hepatic_plasma_clearance_L_per_h"),
        res.get("hepatic_plasma_clearance_mL_per_min"),
        res.get("extraction_ratio_percent"),
        res.get("clearance_classification"),
        row.get("status"),
        row.get("error_message"),
    ]


_EXPORT_HEADERS = [c[0] for c in INPUT_COLUMNS] + OUTPUT_COLUMNS


def export_results_xlsx(results: List[Dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Results"

    ws.append(_EXPORT_HEADERS)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2563EB")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row in results:
        ws.append(_row_for_export(row))

    _autosize(ws)
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_results_csv(results: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(_EXPORT_HEADERS)
    for row in results:
        writer.writerow(_row_for_export(row))
    return buf.getvalue().encode("utf-8")


__all__ = [
    "INPUT_COLUMNS",
    "OUTPUT_COLUMNS",
    "HEADER_DISPLAY",
    "SPECIES_DROPDOWN_VALUES",
    "SYSTEM_DROPDOWN_VALUES",
    "build_template_workbook",
    "parse_uploaded_file",
    "process_rows",
    "export_results_xlsx",
    "export_results_csv",
    "SPECIES_DISPLAY",
]
