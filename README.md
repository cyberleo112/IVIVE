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
2. **Batch (Excel)** — download the input template, fill it in, upload, and
  run. Per-row override columns are supported for any compound. Results can
   be downloaded as `.xlsx` or `.csv`.
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
- **Instructions** — units, accepted aliases, and a reference table of species
defaults.

Aliases accepted in the `species` column: `human`/`man`, `mouse`/`mice`,
`rat`, `dog`/`beagle`, `cyno`/`cynomolgus`/`monkey`/`nhp`. The `system` column
accepts `hepatocyte`/`hep` or `microsome`/`mlm`/`rlm`/`hmm`.

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

