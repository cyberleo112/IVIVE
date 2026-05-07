"""Pydantic request/response models for the IVIVE API."""

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
