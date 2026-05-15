"""Plasma/blood/serum noncompartmental analysis utilities.

The implementation follows conventional NCA/Phoenix-style foundations for
early discovery use: observed Cmax/Tmax, linear-up/log-down AUClast, terminal
log-linear lambda_z, AUC extrapolation, and route-aware CL/Vz labels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence


SUPPORTED_MATRICES = {"plasma", "blood", "serum"}
SUPPORTED_ROUTES = {"extravascular", "iv_bolus", "iv_infusion"}


@dataclass(frozen=True)
class ConcentrationTimePoint:
    time: float
    concentration: float


@dataclass(frozen=True)
class NCAProfileInput:
    compound_id: Optional[str]
    study_id: Optional[str]
    subject_id: Optional[str]
    species: Optional[str]
    matrix: str
    route: str
    dose: float
    dose_unit: str
    time_unit: str
    concentration_unit: str
    observations: List[ConcentrationTimePoint]
    infusion_duration: Optional[float] = None
    terminal_times: Optional[List[float]] = None


@dataclass(frozen=True)
class LambdaZFit:
    lambda_z: float
    intercept: float
    r_squared: float
    adjusted_r_squared: float
    points_used: List[ConcentrationTimePoint]
    method: str


def _validate_profile(profile: NCAProfileInput) -> None:
    if profile.matrix not in SUPPORTED_MATRICES:
        raise ValueError("matrix must be one of: plasma, blood, serum.")
    if profile.route not in SUPPORTED_ROUTES:
        raise ValueError("route must be one of: extravascular, iv_bolus, iv_infusion.")
    if profile.dose <= 0:
        raise ValueError("dose must be greater than 0.")
    if profile.route == "iv_infusion":
        if profile.infusion_duration is None or profile.infusion_duration <= 0:
            raise ValueError("infusion_duration is required for iv_infusion and must be greater than 0.")
    if len(profile.observations) < 2:
        raise ValueError("at least two concentration-time observations are required.")
    for point in profile.observations:
        if point.time < 0:
            raise ValueError("time values must be nonnegative.")
        if point.concentration < 0:
            raise ValueError("concentration values must be nonnegative.")


def _sort_observations(points: Iterable[ConcentrationTimePoint]) -> List[ConcentrationTimePoint]:
    return sorted(points, key=lambda point: point.time)


def _linear_trapezoid(c1: float, c2: float, dt: float) -> float:
    return (c1 + c2) * 0.5 * dt


def _log_trapezoid(c1: float, c2: float, dt: float) -> float:
    if c1 <= 0 or c2 <= 0 or c1 == c2:
        return _linear_trapezoid(c1, c2, dt)
    return (c1 - c2) / math.log(c1 / c2) * dt


def auc_linear_up_log_down(points: Sequence[ConcentrationTimePoint]) -> float:
    """Calculate AUC using linear-up/log-down trapezoids."""
    area = 0.0
    for left, right in zip(points, points[1:]):
        dt = right.time - left.time
        if dt < 0:
            raise ValueError("observations must be sorted by nondecreasing time.")
        if right.concentration < left.concentration:
            area += _log_trapezoid(left.concentration, right.concentration, dt)
        else:
            area += _linear_trapezoid(left.concentration, right.concentration, dt)
    return area


def _linear_moment_trapezoid(left: ConcentrationTimePoint, right: ConcentrationTimePoint) -> float:
    dt = right.time - left.time
    return (left.time * left.concentration + right.time * right.concentration) * 0.5 * dt


def _log_moment_trapezoid(left: ConcentrationTimePoint, right: ConcentrationTimePoint) -> float:
    c1 = left.concentration
    c2 = right.concentration
    dt = right.time - left.time
    if c1 <= 0 or c2 <= 0 or c1 == c2:
        return _linear_moment_trapezoid(left, right)
    kel_interval = math.log(c1 / c2) / dt
    auc_interval = (c1 - c2) / kel_interval
    return left.time * auc_interval + c1 * (1.0 - (c2 / c1) * (1.0 + kel_interval * dt)) / (kel_interval ** 2)


def aumc_linear_up_log_down(points: Sequence[ConcentrationTimePoint]) -> float:
    """Calculate AUMC using linear-up/log-down first-moment trapezoids."""
    area = 0.0
    for left, right in zip(points, points[1:]):
        dt = right.time - left.time
        if dt < 0:
            raise ValueError("observations must be sorted by nondecreasing time.")
        if right.concentration < left.concentration:
            area += _log_moment_trapezoid(left, right)
        else:
            area += _linear_moment_trapezoid(left, right)
    return area


def _linear_regression_lambda(points: Sequence[ConcentrationTimePoint], method: str) -> Optional[LambdaZFit]:
    if len(points) < 3:
        return None
    if any(point.concentration <= 0 for point in points):
        return None
    xs = [point.time for point in points]
    ys = [math.log(point.concentration) for point in points]
    xbar = sum(xs) / len(xs)
    ybar = sum(ys) / len(ys)
    ssxx = sum((x - xbar) ** 2 for x in xs)
    if ssxx <= 0:
        return None
    slope = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / ssxx
    if slope >= 0:
        return None
    intercept = ybar - slope * xbar
    fitted = [intercept + slope * x for x in xs]
    ss_res = sum((y - yhat) ** 2 for y, yhat in zip(ys, fitted))
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    r_squared = 1.0 if ss_tot == 0 else max(0.0, 1.0 - ss_res / ss_tot)
    n = len(points)
    adjusted = 1.0 - (1.0 - r_squared) * (n - 1) / (n - 2)
    return LambdaZFit(
        lambda_z=-slope,
        intercept=intercept,
        r_squared=r_squared,
        adjusted_r_squared=adjusted,
        points_used=list(points),
        method=method,
    )


def _select_manual_terminal_points(
    observations: Sequence[ConcentrationTimePoint],
    terminal_times: Sequence[float],
) -> List[ConcentrationTimePoint]:
    selected: List[ConcentrationTimePoint] = []
    for terminal_time in terminal_times:
        matches = [point for point in observations if math.isclose(point.time, terminal_time, rel_tol=0, abs_tol=1e-9)]
        if not matches:
            raise ValueError(f"terminal time {terminal_time} was not found in observations.")
        selected.append(matches[0])
    return selected


def estimate_lambda_z(
    observations: Sequence[ConcentrationTimePoint],
    route: str,
    tmax: float,
    infusion_duration: Optional[float],
    terminal_times: Optional[Sequence[float]] = None,
) -> Optional[LambdaZFit]:
    """Estimate terminal elimination rate constant using log-linear regression."""
    if terminal_times:
        selected = _select_manual_terminal_points(observations, terminal_times)
        return _linear_regression_lambda(selected, "manual")

    positive = [point for point in observations if point.concentration > 0]
    if route == "iv_bolus":
        candidates = positive
    elif route == "iv_infusion":
        candidates = [
            point for point in positive
            if point.time >= (infusion_duration or 0) and point.time > tmax
        ]
    else:
        candidates = [point for point in positive if point.time > tmax]

    if len(candidates) < 3:
        return None

    best: Optional[LambdaZFit] = None
    for n_points in range(3, len(candidates) + 1):
        fit = _linear_regression_lambda(candidates[-n_points:], "automatic_adjusted_r2")
        if fit is None:
            continue
        if best is None:
            best = fit
            continue
        better_r2 = fit.adjusted_r_squared > best.adjusted_r_squared
        tie_more_points = (
            abs(fit.adjusted_r_squared - best.adjusted_r_squared) <= 0.0001
            and len(fit.points_used) > len(best.points_used)
        )
        if better_r2 or tie_more_points:
            best = fit
    return best


def calculate_profile_nca(profile: NCAProfileInput) -> dict:
    """Calculate NCA parameters for one plasma/blood/serum profile."""
    _validate_profile(profile)
    observations = _sort_observations(profile.observations)
    if len({point.time for point in observations}) != len(observations):
        raise ValueError("duplicate time values are not supported in one NCA profile.")

    cmax = max(point.concentration for point in observations)
    tmax = next(point.time for point in observations if point.concentration == cmax)
    positive_indices = [idx for idx, point in enumerate(observations) if point.concentration > 0]
    if not positive_indices:
        raise ValueError("at least one positive concentration is required.")

    last_positive_index = positive_indices[-1]
    auc_points = observations[: last_positive_index + 1]
    tlast = observations[last_positive_index].time
    clast = observations[last_positive_index].concentration
    auclast = auc_linear_up_log_down(auc_points)
    aumclast = aumc_linear_up_log_down(auc_points)
    mrtlast = aumclast / auclast if auclast > 0 else None
    if mrtlast is not None and profile.route == "iv_infusion":
        mrtlast -= (profile.infusion_duration or 0.0) / 2.0

    warnings: List[str] = []
    fit = estimate_lambda_z(
        observations,
        route=profile.route,
        tmax=tmax,
        infusion_duration=profile.infusion_duration,
        terminal_times=profile.terminal_times,
    )

    lambda_z = None
    half_life = None
    aucinf_obs = None
    auc_percent_extrapolated = None
    aumcinf_obs = None
    mrtinf_obs = None
    clearance = None
    volume_z = None
    volume_ss = None
    r_squared = None
    adjusted_r_squared = None
    terminal_points = []
    clast_pred = None

    if fit is None:
        warnings.append("lambda_z_not_estimable")
    else:
        lambda_z = fit.lambda_z
        half_life = math.log(2.0) / lambda_z
        aucinf_obs = auclast + clast / lambda_z
        auc_percent_extrapolated = 100.0 * (aucinf_obs - auclast) / aucinf_obs
        aumcinf_obs = aumclast + (tlast * clast / lambda_z) + (clast / (lambda_z ** 2))
        mrtinf_obs = aumcinf_obs / aucinf_obs
        if profile.route == "iv_infusion":
            mrtinf_obs -= (profile.infusion_duration or 0.0) / 2.0
        clearance = profile.dose / aucinf_obs
        volume_z = clearance / lambda_z
        r_squared = fit.r_squared
        adjusted_r_squared = fit.adjusted_r_squared
        terminal_points = [point.time for point in fit.points_used]
        clast_pred = math.exp(fit.intercept - lambda_z * tlast)
        if auc_percent_extrapolated > 20:
            warnings.append("auc_extrapolated_gt_20_percent")

    is_iv = profile.route in {"iv_bolus", "iv_infusion"}
    if is_iv and clearance is not None and mrtinf_obs is not None:
        volume_ss = clearance * mrtinf_obs
    elif not is_iv:
        warnings.append("vss_not_calculated_for_extravascular")
    return {
        "compound_id": profile.compound_id,
        "study_id": profile.study_id,
        "subject_id": profile.subject_id,
        "species": profile.species,
        "matrix": profile.matrix,
        "route": profile.route,
        "dose": profile.dose,
        "dose_unit": profile.dose_unit,
        "time_unit": profile.time_unit,
        "concentration_unit": profile.concentration_unit,
        "auc_method": "linear_up_log_down",
        "cmax": cmax,
        "tmax": tmax,
        "tlast": tlast,
        "clast": clast,
        "clast_pred": clast_pred,
        "auclast": auclast,
        "aumclast": aumclast,
        "lambda_z": lambda_z,
        "kel": lambda_z,
        "half_life": half_life,
        "aucinf_obs": aucinf_obs,
        "aumcinf_obs": aumcinf_obs,
        "auc_percent_extrapolated": auc_percent_extrapolated,
        "mrtlast": mrtlast,
        "mrtinf_obs": mrtinf_obs,
        "clearance": clearance,
        "clearance_label": "CL" if is_iv else "CL/F",
        "volume_z": volume_z,
        "volume_z_label": "Vz" if is_iv else "Vz/F",
        "volume_ss": volume_ss,
        "volume_ss_label": "Vss" if is_iv else None,
        "lambda_z_r_squared": r_squared,
        "lambda_z_adjusted_r_squared": adjusted_r_squared,
        "lambda_z_points": terminal_points,
        "lambda_z_method": fit.method if fit else None,
        "warnings": warnings,
    }
