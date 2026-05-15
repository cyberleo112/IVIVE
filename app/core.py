"""Core IVIVE math and species/model defaults.

Single source of truth for hepatic plasma clearance prediction from in vitro
intrinsic clearance, supporting hepatocyte and microsome systems for human,
mouse, rat, dog, and cynomolgus monkey.

Well-stirred / venous equilibrium model:
    CLh,p = Rbp * Qh * CLint,u,liver / (CLint,u,liver + Qh * Rbp / fu_p)
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class SpeciesScalingFactor:
    species: str
    weight_kg: float
    gender_default: str
    liver_blood_flow_L_per_h: float
    liver_weight_g: float
    hepatocytes_million_per_g_liver: float
    microsomal_protein_mg_per_g_liver: float


@dataclass
class IVIVEInput:
    model: str
    model_label: str
    species: str
    system: str
    clint_in_vitro: float
    fu_inc: float
    fu_p: float
    blood_to_plasma_ratio: float
    liver_blood_flow_L_per_h: float
    liver_weight_g: float
    hepatocytes_million_per_g_liver: float
    microsomal_protein_mg_per_g_liver: float


@dataclass
class IVIVEResult:
    species: str
    system: str
    clint_u_in_vitro: float
    total_scaling_amount: float
    scaling_unit: str
    clint_u_liver_L_per_h: float
    hepatic_plasma_clearance_L_per_h: float
    hepatic_plasma_clearance_mL_per_min: float
    plasma_liver_flow_L_per_h: float
    extraction_ratio_plasma: float
    clearance_classification: str


# Clearance classification thresholds based on hepatic extraction ratio (Eh):
#   Low      : Eh < 30%
#   Moderate : 30% <= Eh <= 70%
#   High     : Eh > 70%
CLEARANCE_LOW_MAX_PERCENT: float = 30.0
CLEARANCE_HIGH_MIN_PERCENT: float = 70.0


def classify_clearance(extraction_ratio_percent: float) -> str:
    """Return 'Low', 'Moderate', or 'High' based on hepatic extraction ratio (%).

    Criteria:
      - Low      when Eh < 30%
      - Moderate when 30% <= Eh <= 70%
      - High     when Eh > 70%
    """
    if extraction_ratio_percent < CLEARANCE_LOW_MAX_PERCENT:
        return "Low"
    if extraction_ratio_percent > CLEARANCE_HIGH_MIN_PERCENT:
        return "High"
    return "Moderate"


SPECIES_DEFAULTS: Dict[str, SpeciesScalingFactor] = {
    "human": SpeciesScalingFactor("Human", 70, "Male / adult default", 84.42, 1639, 120, 38),
    "mouse": SpeciesScalingFactor("Mouse", 0.02, "Adult default", 0.1021, 1.424, 120, 37.42),
    "rat": SpeciesScalingFactor("Rat", 0.25, "Adult default", 0.708, 11.02, 120, 38),
    "dog": SpeciesScalingFactor("Dog", 10, "Beagle / adult default", 18.54, 324.5, 120, 61),
    "cyno": SpeciesScalingFactor("Cyno", 4, "Cyno / adult default", 8.72, 100, 120, 38),
}

SIMCYP_SPECIES_DEFAULTS: Dict[str, SpeciesScalingFactor] = {
    "human": SpeciesScalingFactor("Human", 70, "Simcyp adult default", 91.8, 1782.648, 117.52, 39.791),
    "mouse": SpeciesScalingFactor("Mouse", 0.02, "Simcyp default", 0.189216, 1.2852, 135, 48),
    "rat": SpeciesScalingFactor("Rat", 0.25, "Simcyp default", 1.1616, 8.9985, 108, 46),
    "dog": SpeciesScalingFactor("Dog", 10, "Simcyp default", 31.10382, 300, 170, 40.41),
    "cyno": SpeciesScalingFactor("Cyno", 5, "Simcyp monkey default", 8.62872, 78.80004, 123, 31),
}

MODEL_DEFAULTS: Dict[str, Dict[str, SpeciesScalingFactor]] = {
    "gastroplus": SPECIES_DEFAULTS,
    "simcyp": SIMCYP_SPECIES_DEFAULTS,
}

MODEL_DISPLAY: Dict[str, str] = {
    "gastroplus": "GastroPlus",
    "simcyp": "Simcyp",
}

MODEL_ALIASES: Dict[str, str] = {
    "gastroplus": "gastroplus",
    "gastro plus": "gastroplus",
    "gp": "gastroplus",
    "simcyp": "simcyp",
    "both": "both",
    "all": "both",
}

SPECIES_ALIASES: Dict[str, str] = {
    "human": "human", "man": "human",
    "mouse": "mouse", "mice": "mouse",
    "rat": "rat",
    "dog": "dog", "beagle": "dog",
    "cyno": "cyno", "cynomolgus": "cyno", "monkey": "cyno", "nhp": "cyno",
}

SYSTEM_ALIASES: Dict[str, str] = {
    "hepatocyte": "hepatocyte", "hepatocytes": "hepatocyte", "hep": "hepatocyte",
    "microsome": "microsome", "microsomes": "microsome",
    "hmm": "microsome", "mlm": "microsome", "rlm": "microsome",
}

SPECIES_DISPLAY: Dict[str, str] = {
    "human": "Human",
    "mouse": "Mouse",
    "rat": "Rat",
    "dog": "Dog",
    "cyno": "Monkey",
}


def normalize_species(species: str) -> str:
    """Normalize a species string to one of the canonical keys."""
    key = (species or "").strip().lower()
    if key not in SPECIES_ALIASES:
        valid = ", ".join(sorted(SPECIES_DEFAULTS.keys()))
        raise ValueError(f"Unknown species '{species}'. Valid options: {valid}")
    return SPECIES_ALIASES[key]


def normalize_model(model: Optional[str] = None, *, allow_both: bool = False) -> str:
    """Normalize a model/source string to 'gastroplus', 'simcyp', or 'both'."""
    key = (model or "gastroplus").strip().lower()
    if key not in MODEL_ALIASES:
        valid = ", ".join(MODEL_DISPLAY.values())
        raise ValueError(f"Unknown model '{model}'. Valid options: {valid}.")
    normalized = MODEL_ALIASES[key]
    if normalized == "both" and not allow_both:
        raise ValueError("Use either 'GastroPlus' or 'Simcyp' for one calculation.")
    return normalized


def get_species_defaults(species: str, model: Optional[str] = None) -> SpeciesScalingFactor:
    model_key = normalize_model(model)
    return MODEL_DEFAULTS[model_key][normalize_species(species)]


def normalize_system(system: str) -> str:
    """Normalize a system string to 'hepatocyte' or 'microsome'."""
    key = (system or "").strip().lower()
    if key not in SYSTEM_ALIASES:
        raise ValueError("Unknown system. Use 'hepatocyte' or 'microsome'.")
    return SYSTEM_ALIASES[key]


def _validate_fraction(name: str, value: float) -> None:
    if value <= 0 or value > 1:
        raise ValueError(
            f"{name} must be a fraction between 0 and 1 (e.g. 10% = 0.10)."
        )


def calculate_hepatic_clearance(inputs: IVIVEInput) -> IVIVEResult:
    """Predict hepatic plasma clearance using the well-stirred model."""
    _validate_fraction("fu_inc", inputs.fu_inc)
    _validate_fraction("fu_p", inputs.fu_p)

    if inputs.clint_in_vitro < 0:
        raise ValueError("In vitro CLint cannot be negative.")
    if inputs.blood_to_plasma_ratio <= 0:
        raise ValueError("Blood-to-plasma ratio must be greater than 0.")
    if inputs.liver_blood_flow_L_per_h <= 0:
        raise ValueError("Liver blood flow must be greater than 0.")
    if inputs.liver_weight_g <= 0:
        raise ValueError("Liver weight must be greater than 0.")

    clint_u_in_vitro = inputs.clint_in_vitro / inputs.fu_inc

    if inputs.system == "hepatocyte":
        if inputs.hepatocytes_million_per_g_liver <= 0:
            raise ValueError("Hepatocellularity must be greater than 0.")
        total_scaling_amount = inputs.liver_weight_g * inputs.hepatocytes_million_per_g_liver
        scaling_unit = "million cells"
    elif inputs.system == "microsome":
        if inputs.microsomal_protein_mg_per_g_liver <= 0:
            raise ValueError("Microsomal protein per g liver must be greater than 0.")
        total_scaling_amount = inputs.liver_weight_g * inputs.microsomal_protein_mg_per_g_liver
        scaling_unit = "mg microsomal protein"
    else:
        raise ValueError("Unknown system. Use 'hepatocyte' or 'microsome'.")

    clint_u_liver_uL_per_min = clint_u_in_vitro * total_scaling_amount
    clint_u_liver_L_per_h = clint_u_liver_uL_per_min * 1e-6 * 60

    Qh = inputs.liver_blood_flow_L_per_h
    Rbp = inputs.blood_to_plasma_ratio
    fu_p = inputs.fu_p
    CLint_u_liver = clint_u_liver_L_per_h

    hepatic_plasma_clearance_L_per_h = (
        Rbp * Qh * CLint_u_liver / (CLint_u_liver + Qh * Rbp / fu_p)
    )
    hepatic_plasma_clearance_mL_per_min = hepatic_plasma_clearance_L_per_h * 1000 / 60
    plasma_liver_flow_L_per_h = Rbp * Qh
    extraction_ratio_plasma = hepatic_plasma_clearance_L_per_h / plasma_liver_flow_L_per_h

    return IVIVEResult(
        species=inputs.species,
        system=inputs.system,
        clint_u_in_vitro=clint_u_in_vitro,
        total_scaling_amount=total_scaling_amount,
        scaling_unit=scaling_unit,
        clint_u_liver_L_per_h=clint_u_liver_L_per_h,
        hepatic_plasma_clearance_L_per_h=hepatic_plasma_clearance_L_per_h,
        hepatic_plasma_clearance_mL_per_min=hepatic_plasma_clearance_mL_per_min,
        plasma_liver_flow_L_per_h=plasma_liver_flow_L_per_h,
        extraction_ratio_plasma=extraction_ratio_plasma,
        clearance_classification=classify_clearance(extraction_ratio_plasma * 100.0),
    )


def make_input_from_species(
    species: str,
    system: str,
    clint: float,
    fu_inc: float,
    fu_p: float,
    rbp: float,
    model: Optional[str] = None,
    liver_blood_flow_L_per_h: Optional[float] = None,
    liver_weight_g: Optional[float] = None,
    hpgl: Optional[float] = None,
    mppgl: Optional[float] = None,
) -> IVIVEInput:
    """Build an IVIVEInput, filling species defaults for any unspecified fields."""
    model_key = normalize_model(model)
    defaults = get_species_defaults(species, model_key)
    normalized_system = normalize_system(system)
    return IVIVEInput(
        model=model_key,
        model_label=MODEL_DISPLAY[model_key],
        species=defaults.species,
        system=normalized_system,
        clint_in_vitro=clint,
        fu_inc=fu_inc,
        fu_p=fu_p,
        blood_to_plasma_ratio=rbp,
        liver_blood_flow_L_per_h=(
            liver_blood_flow_L_per_h
            if liver_blood_flow_L_per_h is not None
            else defaults.liver_blood_flow_L_per_h
        ),
        liver_weight_g=(
            liver_weight_g if liver_weight_g is not None else defaults.liver_weight_g
        ),
        hepatocytes_million_per_g_liver=(
            hpgl if hpgl is not None else defaults.hepatocytes_million_per_g_liver
        ),
        microsomal_protein_mg_per_g_liver=(
            mppgl if mppgl is not None else defaults.microsomal_protein_mg_per_g_liver
        ),
    )
