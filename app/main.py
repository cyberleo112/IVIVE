"""FastAPI app exposing the IVIVE calculator and serving the static UI."""

import os
from typing import Any, Dict, List

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app import batch as batch_mod
from app.core import (
    SPECIES_DEFAULTS,
    SPECIES_DISPLAY,
    calculate_hepatic_clearance,
    make_input_from_species,
    normalize_species,
)
from app.schemas import (
    BatchExportRequest,
    BatchResponse,
    CalculateRequest,
    CalculateResponse,
    SpeciesDefaultsResponse,
    ValidationResponse,
)
from app import validation as validation_mod


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATIC_DIR = os.path.join(_PROJECT_ROOT, "static")

app = FastAPI(
    title="IVIVE Hepatic Clearance API",
    description=(
        "Predict in vivo hepatic plasma clearance from in vitro hepatocyte or "
        "microsome intrinsic clearance, for human, mouse, rat, dog, and "
        "cynomolgus monkey. Endpoints are designed to be reusable as agent "
        "tools and from a database-backed workflow."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/species", response_model=List[SpeciesDefaultsResponse])
def get_species() -> List[SpeciesDefaultsResponse]:
    """Return canonical species keys, display labels, and default scaling factors."""
    out: List[SpeciesDefaultsResponse] = []
    for key, sf in SPECIES_DEFAULTS.items():
        out.append(SpeciesDefaultsResponse(
            key=key,
            label=SPECIES_DISPLAY[key],
            weight_kg=sf.weight_kg,
            gender_default=sf.gender_default,
            liver_blood_flow_L_per_h=sf.liver_blood_flow_L_per_h,
            liver_weight_g=sf.liver_weight_g,
            hepatocytes_million_per_g_liver=sf.hepatocytes_million_per_g_liver,
            microsomal_protein_mg_per_g_liver=sf.microsomal_protein_mg_per_g_liver,
        ))
    return out


def _to_calculate_response(*, ivive_input, result, compound_id, species_key):
    return CalculateResponse(
        compound_id=compound_id,
        species=ivive_input.species,
        species_key=species_key,
        system=ivive_input.system,
        inputs_used={
            "clint_in_vitro": ivive_input.clint_in_vitro,
            "fu_inc": ivive_input.fu_inc,
            "fu_p": ivive_input.fu_p,
            "rbp": ivive_input.blood_to_plasma_ratio,
            "liver_blood_flow_L_per_h": ivive_input.liver_blood_flow_L_per_h,
            "liver_weight_g": ivive_input.liver_weight_g,
            "hpgl": ivive_input.hepatocytes_million_per_g_liver,
            "mppgl": ivive_input.microsomal_protein_mg_per_g_liver,
        },
        clint_u_in_vitro=result.clint_u_in_vitro,
        total_scaling_amount=result.total_scaling_amount,
        scaling_unit=result.scaling_unit,
        clint_u_liver_L_per_h=result.clint_u_liver_L_per_h,
        plasma_liver_flow_L_per_h=result.plasma_liver_flow_L_per_h,
        hepatic_plasma_clearance_L_per_h=result.hepatic_plasma_clearance_L_per_h,
        hepatic_plasma_clearance_mL_per_min=result.hepatic_plasma_clearance_mL_per_min,
        extraction_ratio_plasma=result.extraction_ratio_plasma,
        extraction_ratio_percent=result.extraction_ratio_plasma * 100.0,
    )


@app.post("/api/calculate", response_model=CalculateResponse)
def calculate(req: CalculateRequest) -> CalculateResponse:
    """Single-compound IVIVE calculation."""
    try:
        species_key = normalize_species(req.species)
        ivive_input = make_input_from_species(
            species=req.species,
            system=req.system,
            clint=req.clint_in_vitro,
            fu_inc=req.fu_inc,
            fu_p=req.fu_p,
            rbp=req.rbp,
            liver_blood_flow_L_per_h=req.liver_blood_flow_L_per_h,
            liver_weight_g=req.liver_weight_g,
            hpgl=req.hpgl,
            mppgl=req.mppgl,
        )
        result = calculate_hepatic_clearance(ivive_input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _to_calculate_response(
        ivive_input=ivive_input,
        result=result,
        compound_id=req.compound_id,
        species_key=species_key,
    )


@app.get("/api/template")
def get_template() -> Response:
    """Download the .xlsx batch input template."""
    data = batch_mod.build_template_workbook()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="ivive_template.xlsx"'},
    )


@app.post("/api/batch", response_model=BatchResponse)
async def run_batch(file: UploadFile = File(...)) -> BatchResponse:
    """Parse an uploaded .xlsx or .csv batch file and run IVIVE on each row."""
    try:
        content = await file.read()
        rows = batch_mod.parse_uploaded_file(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc

    results = batch_mod.process_rows(rows)
    success = sum(1 for r in results if r["status"] == "ok")
    return BatchResponse(
        total_rows=len(results),
        success_count=success,
        error_count=len(results) - success,
        results=results,
    )


@app.post("/api/batch/export")
def export_batch(req: BatchExportRequest, format: str = "xlsx") -> Response:
    """Export a batch results array as .xlsx (default) or .csv."""
    fmt = (format or "xlsx").lower()
    rows: List[Dict[str, Any]] = [r.model_dump() for r in req.results]
    if fmt == "csv":
        data = batch_mod.export_results_csv(rows)
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="ivive_results.csv"'},
        )
    if fmt == "xlsx":
        data = batch_mod.export_results_xlsx(rows)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="ivive_results.xlsx"'},
        )
    raise HTTPException(status_code=400, detail="format must be 'xlsx' or 'csv'.")


@app.get(
    "/api/validation",
    response_model=ValidationResponse,
    response_model_by_alias=True,
)
def get_validation() -> ValidationResponse:
    """Run the 11 built-in validation cases and return pass/fail summary."""
    payload = validation_mod.run_all()
    return ValidationResponse.model_validate(payload)


# --- static frontend ---


@app.get("/")
def root() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
