# IVIVE Hepatic Clearance Web App

A simple browser-based calculator that predicts in vivo hepatic plasma clearance
(`CL_p`) and extraction ratio (`E_h`) from in vitro intrinsic clearance for two
systems and five species:

- **Systems:** Hepatocytes, Microsomes
- **Species:** Human, Mouse, Rat, Dog, Cynomolgus monkey

It supports both **single-compound** entry and **batch** processing via Excel
upload, plus a built-in **validation** tab that runs 11 reference cases from
`IVIVE validation.md`.

## Model

Well-stirred (venous equilibrium):

```
CL_int,u,liver = (CL_int / fu_inc) * (liver_weight_g * scaling) * 1e-6 * 60   [L/h]
CL_p           = R_bp * Q_h * CL_int,u,liver / (CL_int,u,liver + Q_h * R_bp / fu_p)
E_h            = CL_p / (R_bp * Q_h)
```

Where `scaling` is HPGL (M cells / g liver) for hepatocytes or MPPGL (mg / g
liver) for microsomes.

### Clearance classification

The predicted hepatic extraction ratio (`E_h`, expressed as a percentage) is
classified as:

| Class    | Criterion             |
| -------- | --------------------- |
| Low      | `E_h < 30%`           |
| Moderate | `30% <= E_h <= 70%`   |
| High     | `E_h > 70%`           |

The classification is returned by the API as
`clearance_classification` on the single calculation response and on each batch
row, and is also shown in the UI under "Predicted in vivo clearance" and as a
column in the batch results table / exported file.

## Quick start

Requires Python 3.10+.

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# then open http://localhost:8000/
```

To run the validation tests via pytest:

```bash
pytest -q
```

The original CLI still works:

```bash
python "Hepatocyte and Microsomes Clearance IVIVE.py" --show-species
python "Hepatocyte and Microsomes Clearance IVIVE.py" \
    --species human --system hepatocyte \
    --clint 6.4 --fu-inc 0.76 --fu-p 0.023 --rbp 0.667
```

## Web UI

Three tabs:

1. **Single** — pick species + system, enter CLint, fu_inc, fu_p, Rbp; an
  optional Advanced section lets you override Q_h, liver weight, HPGL, MPPGL.
  The result panel shows `CL_p`, `E_h`, and a Low / Moderate / High
  classification.
2. **Batch (Excel)** — download the input template, fill it in, upload, and
  run. Species and in-vitro system are dropdowns in the template; CLint /
  fu_inc / fu_p columns show units and accepted ranges (matching the single
  UI). Per-row override columns are supported for any compound. Results
  include a clearance classification column and can be downloaded as `.xlsx`
  or `.csv`.
3. **Validation** — runs the 11 reference cases and reports pass/fail with
  tolerances ±2% on CL_p and ±0.5 pp on E_h.

## API endpoints (designed for reuse as agent tools later)


| Method | Path                        | Purpose                                   |
| ------ | --------------------------- | ----------------------------------------- |
| GET    | `/api/species`              | Species defaults (Q_h, liver, HPGL/MPPGL) |
| POST   | `/api/calculate`            | Single-compound IVIVE calculation         |
| GET    | `/api/template`             | Download `.xlsx` batch input template     |
| POST   | `/api/batch`                | Upload `.xlsx`/`.csv`; returns JSON       |
| POST   | `/api/batch/export?format=` | Export batch results as `xlsx` or `csv`   |
| GET    | `/api/validation`           | Run the 11 built-in validation cases      |


OpenAPI docs auto-generated at `http://localhost:8000/docs`.

### Example: single-compound calculation

```bash
curl -s http://localhost:8000/api/calculate \
  -H 'Content-Type: application/json' \
  -d '{
    "species": "human", "system": "hepatocyte",
    "clint_in_vitro": 6.4, "fu_inc": 0.76, "fu_p": 0.023, "rbp": 0.667
  }'
```

## Excel template

`/api/template` returns a workbook with two sheets:

- **Inputs** — required columns `compound_id`, `species`, `system`,
`clint_in_vitro`, `fu_inc`, `fu_p`, `rbp`, plus optional override columns
`liver_blood_flow_L_per_h`, `liver_weight_g`, `hpgl`, `mppgl`. Two example
rows are pre-filled.
  - **Dropdowns** — `species` is a dropdown with `human / mouse / rat / dog /
    monkey`, and `system` is a dropdown with `hepatocyte / microsome`.
  - **Units & ranges in headers** — `clint_in_vitro` shows
    `uL/min/million cells (hep) or uL/min/mg (mic)`, and `fu_inc` / `fu_p`
    show the accepted `0 < value <= 1` range, matching the single-compound UI.
    Excel data validation also enforces these ranges and CLint >= 0.
- **Instructions** — units, accepted aliases, and a reference table of species
defaults.

Aliases accepted in the `species` column: `human`/`man`, `mouse`/`mice`,
`rat`, `dog`/`beagle`, `cyno`/`cynomolgus`/`monkey`/`nhp`. The `system` column
accepts `hepatocyte`/`hep` or `microsome`/`mlm`/`rlm`/`hmm`. Headers may
include unit/range hints in parentheses (matching the template); they are
stripped automatically when parsing.

Exported batch result files include a `clearance_classification` column
(Low / Moderate / High) alongside `clp_L_per_h`, `clp_mL_per_min`, and
`eh_percent`.

## Project layout

```
app/
  core.py        # IVIVE math + species defaults (single source of truth)
  schemas.py     # Pydantic request/response models
  batch.py       # Excel template + batch I/O
  validation.py  # 11 built-in validation cases
  main.py        # FastAPI app + routes + static mount
static/
  index.html     # Single page, three tabs
  app.js         # Vanilla JS frontend
tests/
  test_ivive.py  # pytest over all 11 validation cases
Hepatocyte and Microsomes Clearance IVIVE.py   # original CLI (now imports app.core)
IVIVE validation.md                             # source of validation cases
```

## Roadmap

- Add database persistence for runs and uploaded compounds.
- Add an LLM agent that calls `/api/calculate` and `/api/batch` as tools and
interprets results (e.g., flag high-extraction compounds).
- Optional intermediate-value display in the UI (already in API payload).

