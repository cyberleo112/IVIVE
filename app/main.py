"""FastAPI app exposing the IVIVE calculator and serving the static UI."""

import os
from typing import Any, Dict, List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app import allometry as allometry_mod
from app import batch as batch_mod
from app import comparison as comparison_mod
from app import nca as nca_mod
from app.core import (
    MODEL_DEFAULTS,
    MODEL_DISPLAY,
    SPECIES_DISPLAY,
    calculate_hepatic_clearance,
    make_input_from_species,
    normalize_model,
    normalize_species,
)
from app.schemas import (
    BatchExportRequest,
    BatchResponse,
    CalculateRequest,
    CalculateResponse,
    AllometryScaleRequest,
    AllometryScaleResponse,
    NCAPlasmaRequest,
    NCAPlasmaResponse,
    PredictionCompareRequest,
    PredictionCompareResponse,
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
def get_species(model: str = "gastroplus") -> List[SpeciesDefaultsResponse]:
    """Return canonical species keys, display labels, and default scaling factors."""
    try:
        model_key = normalize_model(model, allow_both=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    model_keys = list(MODEL_DEFAULTS.keys()) if model_key == "both" else [model_key]
    out: List[SpeciesDefaultsResponse] = []
    for source_key in model_keys:
        for key, sf in MODEL_DEFAULTS[source_key].items():
            out.append(SpeciesDefaultsResponse(
                model=source_key,
                model_label=MODEL_DISPLAY[source_key],
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
        model=ivive_input.model,
        model_label=ivive_input.model_label,
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
        clearance_classification=result.clearance_classification,
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
            model=req.model,
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
async def run_batch(
    file: UploadFile = File(...),
    model: str = Form(default=""),
) -> BatchResponse:
    """Parse an uploaded .xlsx or .csv batch file and run IVIVE on each row."""
    try:
        content = await file.read()
        rows = batch_mod.parse_uploaded_file(file.filename or "", content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc

    results = batch_mod.process_rows(rows, model_override=model)
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


@app.post("/api/nca/plasma", response_model=NCAPlasmaResponse)
def calculate_plasma_nca(req: NCAPlasmaRequest) -> NCAPlasmaResponse:
    """Run plasma/blood/serum NCA for one or more concentration-time profiles."""
    results = []
    try:
        for profile in req.profiles:
            nca_input = nca_mod.NCAProfileInput(
                compound_id=profile.compound_id,
                study_id=profile.study_id,
                subject_id=profile.subject_id,
                species=profile.species,
                matrix=profile.matrix,
                route=profile.route,
                dose=profile.dose,
                dose_unit=profile.dose_unit,
                time_unit=profile.time_unit,
                concentration_unit=profile.concentration_unit,
                observations=[
                    nca_mod.ConcentrationTimePoint(
                        time=obs.time,
                        concentration=obs.concentration,
                    )
                    for obs in profile.observations
                ],
                infusion_duration=profile.infusion_duration,
                terminal_times=profile.terminal_times,
            )
            results.append(nca_mod.calculate_profile_nca(nca_input))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return NCAPlasmaResponse(total_profiles=len(results), profiles=results)


@app.post("/api/allometry/scale", response_model=AllometryScaleResponse)
def scale_allometry(req: AllometryScaleRequest) -> AllometryScaleResponse:
    """Run standalone allometric scaling from species-level PK parameters."""
    try:
        payload = allometry_mod.scale_allometry(
            allometry_mod.AllometryInput(
                rows=[
                    allometry_mod.AllometrySpeciesInput(
                        species=row.species,
                        body_weight_kg=row.body_weight_kg,
                        parameter=row.parameter,
                        value=row.value,
                        unit=row.unit,
                        route=row.route,
                        bioavailability_known=row.bioavailability_known,
                    )
                    for row in req.rows
                ],
                target_species=req.target_species,
                target_body_weight_kg=req.target_body_weight_kg,
                fixed_exponent=req.fixed_exponent,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AllometryScaleResponse.model_validate(payload)


@app.post("/api/prediction/compare", response_model=PredictionCompareResponse)
def compare_prediction(req: PredictionCompareRequest) -> PredictionCompareResponse:
    """Compare observed and predicted PK parameters by fold error."""
    try:
        comparisons = comparison_mod.compare_predictions(
            [row.model_dump() for row in req.observed],
            [row.model_dump() for row in req.predicted],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PredictionCompareResponse(
        total_comparisons=len(comparisons),
        comparisons=comparisons,
    )


# --- static frontend ---


@app.get("/")
def root() -> FileResponse:
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
