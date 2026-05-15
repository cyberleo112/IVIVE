"""Pydantic request/response models for the IVIVE and PK prediction APIs."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class CalculateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = Field(default="gastroplus", description="GastroPlus or Simcyp.")
    species: str = Field(..., description="One of human, mouse, rat, dog, cyno/monkey.")
    system: str = Field(..., description="hepatocyte or microsome.")
    clint_in_vitro: float = Field(..., ge=0, description="uL/min/million cells (hep) or uL/min/mg (mic).")
    fu_inc: float = Field(..., gt=0, le=1, description="Fraction unbound in incubation (0-1).")
    fu_p: float = Field(..., gt=0, le=1, description="Fraction unbound in plasma (0-1).")
    rbp: float = Field(..., gt=0, description="Blood-to-plasma concentration ratio.")

    liver_blood_flow_L_per_h: Optional[float] = Field(
        default=None, gt=0, description="Optional override for Qh (L/h)."
    )
    liver_weight_g: Optional[float] = Field(
        default=None, gt=0, description="Optional override for liver weight (g)."
    )
    hpgl: Optional[float] = Field(
        default=None, gt=0, description="Optional override for hepatocytes (million/g liver)."
    )
    mppgl: Optional[float] = Field(
        default=None, gt=0, description="Optional override for microsomal protein (mg/g liver)."
    )
    compound_id: Optional[str] = Field(
        default=None, description="Optional free-text compound label."
    )


class CalculateResponse(BaseModel):
    compound_id: Optional[str] = None
    model: str
    model_label: str
    species: str
    species_key: str
    system: str
    inputs_used: Dict[str, Any]
    clint_u_in_vitro: float
    total_scaling_amount: float
    scaling_unit: str
    clint_u_liver_L_per_h: float
    plasma_liver_flow_L_per_h: float
    hepatic_plasma_clearance_L_per_h: float
    hepatic_plasma_clearance_mL_per_min: float
    extraction_ratio_plasma: float
    extraction_ratio_percent: float
    clearance_classification: str


class SpeciesDefaultsResponse(BaseModel):
    model: str
    model_label: str
    key: str
    label: str
    weight_kg: float
    gender_default: str
    liver_blood_flow_L_per_h: float
    liver_weight_g: float
    hepatocytes_million_per_g_liver: float
    microsomal_protein_mg_per_g_liver: float


class BatchRowResult(BaseModel):
    row: int
    compound_id: Optional[str] = None
    model: Optional[str] = None
    model_label: Optional[str] = None
    species: Optional[str] = None
    system: Optional[str] = None
    status: Literal["ok", "error"]
    error_message: Optional[str] = None
    result: Optional[CalculateResponse] = None


class BatchResponse(BaseModel):
    total_rows: int
    success_count: int
    error_count: int
    results: List[BatchRowResult]


class ValidationCaseResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    case_id: str
    compound: str
    species: str
    system: str
    expected_clp_L_per_h: float
    expected_eh_percent: float
    predicted_clp_L_per_h: float
    predicted_eh_percent: float
    clp_relative_error_percent: float
    eh_absolute_error_pp: float
    pass_: bool = Field(alias="pass")


class ValidationResponse(BaseModel):
    total: int
    passed: int
    failed: int
    clp_relative_tolerance_percent: float
    eh_absolute_tolerance_pp: float
    cases: List[ValidationCaseResult]


class BatchExportRequest(BaseModel):
    results: List[BatchRowResult]


class NCAObservation(BaseModel):
    time: float = Field(..., ge=0)
    concentration: float = Field(..., ge=0)


class NCAProfileRequest(BaseModel):
    compound_id: Optional[str] = None
    study_id: Optional[str] = None
    subject_id: Optional[str] = None
    species: Optional[str] = None
    matrix: Literal["plasma", "blood", "serum"] = "plasma"
    route: Literal["extravascular", "iv_bolus", "iv_infusion"]
    dose: float = Field(..., gt=0)
    dose_unit: str = Field(default="mg")
    time_unit: str = Field(default="h")
    concentration_unit: str = Field(default="ng/mL")
    observations: List[NCAObservation] = Field(..., min_length=2)
    infusion_duration: Optional[float] = Field(default=None, gt=0)
    terminal_times: Optional[List[float]] = None


class NCAPlasmaRequest(BaseModel):
    profiles: List[NCAProfileRequest] = Field(..., min_length=1)


class NCAProfileResponse(BaseModel):
    compound_id: Optional[str] = None
    study_id: Optional[str] = None
    subject_id: Optional[str] = None
    species: Optional[str] = None
    matrix: str
    route: str
    dose: float
    dose_unit: str
    time_unit: str
    concentration_unit: str
    auc_method: str
    cmax: float
    tmax: float
    tlast: float
    clast: float
    clast_pred: Optional[float] = None
    auclast: float
    aumclast: float
    lambda_z: Optional[float] = None
    kel: Optional[float] = None
    half_life: Optional[float] = None
    aucinf_obs: Optional[float] = None
    aumcinf_obs: Optional[float] = None
    auc_percent_extrapolated: Optional[float] = None
    mrtlast: Optional[float] = None
    mrtinf_obs: Optional[float] = None
    clearance: Optional[float] = None
    clearance_label: str
    volume_z: Optional[float] = None
    volume_z_label: str
    volume_ss: Optional[float] = None
    volume_ss_label: Optional[str] = None
    lambda_z_r_squared: Optional[float] = None
    lambda_z_adjusted_r_squared: Optional[float] = None
    lambda_z_points: List[float]
    lambda_z_method: Optional[str] = None
    warnings: List[str]


class NCAPlasmaResponse(BaseModel):
    total_profiles: int
    profiles: List[NCAProfileResponse]


class AllometrySpeciesRow(BaseModel):
    species: str
    body_weight_kg: float = Field(..., gt=0)
    parameter: str
    value: float = Field(..., gt=0)
    unit: str
    route: Optional[str] = None
    bioavailability_known: Optional[bool] = None


class AllometryScaleRequest(BaseModel):
    rows: List[AllometrySpeciesRow] = Field(..., min_length=1)
    target_species: str = "human"
    target_body_weight_kg: float = Field(default=70.0, gt=0)
    fixed_exponent: Optional[float] = None


class AllometryScaleResponse(BaseModel):
    parameter: str
    unit: str
    target_species: str
    target_body_weight_kg: float
    predicted_value: float
    method: str
    coefficient: float
    exponent: float
    r_squared: Optional[float] = None
    species_count: int
    species_used: List[str]
    flags: List[str]


class PKParameterRow(BaseModel):
    compound_id: Optional[str] = None
    species: Optional[str] = None
    parameter: str
    value: float = Field(..., gt=0)
    unit: str
    method: Optional[str] = None
    source: Optional[str] = None


class PredictionCompareRequest(BaseModel):
    observed: List[PKParameterRow] = Field(..., min_length=1)
    predicted: List[PKParameterRow] = Field(..., min_length=1)


class PredictionComparisonRow(BaseModel):
    compound_id: Optional[str] = None
    species: Optional[str] = None
    parameter: str
    unit: str
    observed_value: float
    predicted_value: float
    observed_method: Optional[str] = None
    predicted_method: Optional[str] = None
    predicted_to_observed_ratio: float
    fold_error: float
    percent_error: float
    within_2_fold: bool
    within_3_fold: bool


class PredictionCompareResponse(BaseModel):
    total_comparisons: int
    comparisons: List[PredictionComparisonRow]
