"""Canonical longitudinal analytics: Observation -> FeatureValue -> BaselineVersion -> ChangeSignal.

Deterministic, local statistics adapted from structural-v2 ideas in baseline.py.
This path never calculates clinical RiskAssessment and never calls an LLM.
Risk/safety remains on /api/v1/safety/evaluate via the risk engine.
"""
from __future__ import annotations

import logging
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models_vnext import (
    BaselineVersion,
    ChangeSignal,
    FeatureDefinition,
    FeatureValue,
    Observation,
)
from app.services.baseline import (
    BASELINE_WINDOW_DAYS,
    RECENT_WINDOW_DAYS,
    STD_FLOORS,
    _deviation_band,
    _finite_number,
    _mean_std,
)
from app.utils import as_utc as _utc

logger = logging.getLogger("psychapp.trajectory")

ALGORITHM_VERSION = "canonical-structural-v1"
FEATURE_VERSION = "v1"

MIN_OBS_FOR_BASELINE = 5

# Observation.type values dual-written from check-ins.
OBSERVATION_TYPES = ("mood", "craving", "sleep_hours", "self_efficacy")

# Internal axis keys used for z-scoring (craving inverted: lower craving = higher score).
AXIS_FOR_TYPE = {
    "mood": "mood",
    "craving": "craving_inv",
    "sleep_hours": "sleep_hours",
    "self_efficacy": "self_efficacy",
}
AXES = ("mood", "craving_inv", "sleep_hours", "self_efficacy")


@dataclass
class CanonicalAnalyticsResult:
    status: str
    correlation_id: uuid.UUID
    algorithm_version: str = ALGORITHM_VERSION
    feature_values: list[FeatureValue] = field(default_factory=list)
    baseline_version: BaselineVersion | None = None
    change_signals: list[ChangeSignal] = field(default_factory=list)
    feature_keys: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_response(self) -> dict[str, Any]:
        bv = self.baseline_version
        return {
            "status": self.status,
            "correlation_id": str(self.correlation_id),
            "algorithm_version": self.algorithm_version,
            "feature_keys": list(self.feature_keys),
            "baseline_version": None
            if bv is None
            else {
                "id": str(bv.id),
                "status": bv.status,
                "stability": bv.stability,
                "data_coverage": bv.data_coverage,
                "window": {"start": bv.window_start, "end": bv.window_end},
                "algorithm_version": bv.algorithm_version,
                "stats_keys": sorted((bv.stats or {}).keys()),
            },
            "feature_values": [
                {
                    "id": str(fv.id),
                    "feature_key": fv.feature_key,
                    "feature_version": fv.feature_version,
                    "value": fv.value,
                    "window": {"start": fv.window_start, "end": fv.window_end},
                    "observation_refs": fv.observation_refs,
                    "algorithm_version": fv.algorithm_version,
                    "quality_flags": fv.quality_flags,
                }
                for fv in self.feature_values
            ],
            "change_signals": [
                {
                    "id": str(cs.id),
                    "feature": cs.feature,
                    "band": cs.band,
                    "change_value": cs.change_value,
                    "window": {"start": cs.window_start, "end": cs.window_end},
                    "baseline_version_id": str(cs.baseline_version_id) if cs.baseline_version_id else None,
                    "evidence_refs": cs.evidence_refs,
                    "uncertainty": cs.uncertainty,
                    "algorithm_version": cs.algorithm_version,
                }
                for cs in self.change_signals
            ],
            "detail": self.detail,
        }


def _now_utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return _utc(now)  # type: ignore[return-value]


def _extract_raw(observation: Observation) -> float | None:
    payload = observation.value if isinstance(observation.value, dict) else {}
    raw = _finite_number(payload.get("value"))
    if raw is None:
        return None
    obs_type = observation.type
    upper = 24.0 if obs_type == "sleep_hours" else 10.0
    if not 0.0 <= raw <= upper:
        return None
    return raw


def _to_axis_value(obs_type: str, raw: float) -> float:
    if obs_type == "craving":
        return 10.0 - raw
    return raw


def _ensure_feature_definitions(db: Session) -> dict[str, FeatureDefinition]:
    """Best-effort active FeatureDefinition lookup/seed; never blocks analytics."""
    found: dict[str, FeatureDefinition] = {}
    for obs_type in OBSERVATION_TYPES:
        row = (
            db.query(FeatureDefinition)
            .filter(
                FeatureDefinition.feature_key == obs_type,
                FeatureDefinition.status == "active",
            )
            .order_by(FeatureDefinition.created_at.desc())
            .first()
        )
        if row is None:
            unit = "hours" if obs_type == "sleep_hours" else "0-10"
            row = FeatureDefinition(
                feature_key=obs_type,
                version=FEATURE_VERSION,
                formula=f"mean({obs_type}) over recent window; craving inverted for z-score",
                unit=unit,
                window_spec={
                    "baseline_days": BASELINE_WINDOW_DAYS,
                    "recent_days": RECENT_WINDOW_DAYS,
                    "min_n": MIN_OBS_FOR_BASELINE,
                },
                missingness_policy="missing_is_not_zero; axis omitted from composite when absent",
                valid_range={"min": 0.0, "max": 24.0 if obs_type == "sleep_hours" else 10.0},
                status="active",
            )
            db.add(row)
            db.flush()
        found[obs_type] = row
    return found


def _load_typed_observations(
    db: Session,
    user_id,
    window_start: datetime,
    window_end: datetime,
) -> dict[str, list[tuple[Observation, float]]]:
    rows = (
        db.query(Observation)
        .filter(
            Observation.user_id == user_id,
            Observation.type.in_(list(OBSERVATION_TYPES)),
            Observation.occurred_at >= window_start,
            Observation.occurred_at <= window_end,
        )
        .order_by(Observation.occurred_at.asc())
        .all()
    )
    by_type: dict[str, list[tuple[Observation, float]]] = {t: [] for t in OBSERVATION_TYPES}
    for row in rows:
        raw = _extract_raw(row)
        if raw is None:
            continue
        by_type[row.type].append((row, raw))
    return by_type


def _axis_stats_from_obs(
    by_type: dict[str, list[tuple[Observation, float]]],
) -> dict[str, dict[str, float]]:
    stats: dict[str, dict[str, float]] = {}
    for obs_type in OBSERVATION_TYPES:
        axis = AXIS_FOR_TYPE[obs_type]
        values = [_to_axis_value(obs_type, raw) for _, raw in by_type.get(obs_type, [])]
        if not values:
            continue
        mean, std = _mean_std(values)
        stats[axis] = {
            "mean": round(mean, 6),
            "std": round(std, 6),
            "n": float(len(values)),
            "observation_type": obs_type,
        }
    return stats


def run_canonical_analytics(
    db: Session,
    user_id,
    *,
    now: datetime | None = None,
    correlation_id: uuid.UUID | None = None,
) -> CanonicalAnalyticsResult:
    """Compute and persist FeatureValue, BaselineVersion, and ChangeSignal from Observations."""
    current = _now_utc(now)
    corr = correlation_id or uuid.uuid4()
    definitions = _ensure_feature_definitions(db)

    baseline_start = current - timedelta(days=BASELINE_WINDOW_DAYS)
    recent_start = current - timedelta(days=RECENT_WINDOW_DAYS)

    baseline_obs = _load_typed_observations(db, user_id, baseline_start, current)
    recent_obs = _load_typed_observations(db, user_id, recent_start, current)

    baseline_stats = _axis_stats_from_obs(baseline_obs)
    eligible_axes = [
        axis
        for axis in AXES
        if axis in baseline_stats and baseline_stats[axis]["n"] >= MIN_OBS_FOR_BASELINE
    ]
    coverage = len(eligible_axes) / float(len(AXES))

    if len(eligible_axes) == len(AXES):
        baseline_status = "active"
        stability = "eligible"
    elif eligible_axes:
        baseline_status = "provisional"
        stability = "partial"
    else:
        baseline_status = "provisional"
        stability = "insufficient_data"

    # Supersede prior active/provisional rows for this user (append-only history).
    db.query(BaselineVersion).filter(
        BaselineVersion.user_id == user_id,
        BaselineVersion.status.in_(["active", "provisional"]),
        BaselineVersion.algorithm_version == ALGORITHM_VERSION,
    ).update({"status": "superseded"}, synchronize_session=False)

    baseline_row = BaselineVersion(
        user_id=user_id,
        feature_key=None,
        window_start=baseline_start,
        window_end=current,
        stats=baseline_stats,
        exclusions=[],
        stability=stability,
        data_coverage=round(coverage, 4),
        status=baseline_status,
        algorithm_version=ALGORITHM_VERSION,
    )
    db.add(baseline_row)
    db.flush()

    feature_values: list[FeatureValue] = []
    feature_keys: list[str] = []
    change_signals: list[ChangeSignal] = []
    z_scores: dict[str, float] = {}
    abs_z_values: list[float] = []

    for obs_type in OBSERVATION_TYPES:
        axis = AXIS_FOR_TYPE[obs_type]
        recent_pairs = recent_obs.get(obs_type, [])
        recent_values = [_to_axis_value(obs_type, raw) for _, raw in recent_pairs]
        obs_refs = [str(obs.id) for obs, _ in recent_pairs]
        defn = definitions.get(obs_type)
        feature_version = defn.version if defn is not None else FEATURE_VERSION

        quality_flags: list[str] = []
        if not recent_values:
            quality_flags.append("no_recent_observations")
            fv_payload: dict[str, Any] = {
                "mean": None,
                "n": 0,
                "axis": axis,
                "missing": True,
            }
        else:
            recent_mean = statistics.fmean(recent_values)
            fv_payload = {
                "mean": round(recent_mean, 6),
                "n": len(recent_values),
                "axis": axis,
                "missing": False,
            }

        fv = FeatureValue(
            user_id=user_id,
            feature_key=obs_type,
            feature_version=feature_version,
            value=fv_payload,
            window_start=recent_start,
            window_end=current,
            observation_refs=obs_refs,
            algorithm_version=ALGORITHM_VERSION,
            quality_flags=quality_flags,
        )
        db.add(fv)
        db.flush()
        feature_values.append(fv)
        feature_keys.append(obs_type)

        # Change detection: never fabricate zeros for missing data.
        band = "insufficient_data"
        change_value: float | None = None
        uncertainty: dict[str, Any] = {"reason": None}
        evidence_refs: list[dict[str, str]] = [
            {"kind": "feature_value", "id": str(fv.id)},
            {"kind": "baseline_version", "id": str(baseline_row.id)},
        ]
        evidence_refs.extend({"kind": "observation", "id": oid} for oid in obs_refs)

        axis_stats = baseline_stats.get(axis)
        if (
            fv_payload.get("mean") is not None
            and axis_stats is not None
            and axis_stats["n"] >= MIN_OBS_FOR_BASELINE
        ):
            mean_b = axis_stats["mean"]
            std_b = axis_stats["std"]
            effective_std = max(std_b, STD_FLOORS[axis])
            z = (fv_payload["mean"] - mean_b) / effective_std
            z_scores[axis] = round(z, 6)
            abs_z_values.append(abs(z))
            change_value = round(z, 6)
            band = _deviation_band(abs(z))
            uncertainty = {
                "effective_std": effective_std,
                "baseline_n": int(axis_stats["n"]),
                "recent_n": int(fv_payload["n"]),
            }
        else:
            uncertainty = {
                "reason": "insufficient_baseline_or_recent",
                "baseline_n": int(axis_stats["n"]) if axis_stats else 0,
                "recent_n": int(fv_payload.get("n") or 0),
            }

        cs = ChangeSignal(
            user_id=user_id,
            feature=obs_type,
            window_start=recent_start,
            window_end=current,
            change_value=change_value,
            band=band,
            uncertainty=uncertainty,
            evidence_refs=evidence_refs,
            contradictions=[],
            baseline_version_id=baseline_row.id,
            algorithm_version=ALGORITHM_VERSION,
        )
        db.add(cs)
        db.flush()
        change_signals.append(cs)

    # Composite structural change signal (still a ChangeSignal, not RiskAssessment).
    if len(z_scores) == len(AXES):
        composite_z = statistics.fmean(abs_z_values)
        composite_band = _deviation_band(composite_z)
        composite_change = round(composite_z, 6)
    else:
        composite_z = None
        composite_band = "insufficient_data"
        composite_change = None

    composite = ChangeSignal(
        user_id=user_id,
        feature="structural_composite",
        window_start=recent_start,
        window_end=current,
        change_value=composite_change,
        band=composite_band,
        uncertainty={
            "z_scores": z_scores,
            "axes_present": sorted(z_scores.keys()),
            "axes_required": list(AXES),
        },
        evidence_refs=[
            {"kind": "baseline_version", "id": str(baseline_row.id)},
            *[{"kind": "feature_value", "id": str(fv.id)} for fv in feature_values],
            *[{"kind": "change_signal", "id": str(cs.id)} for cs in change_signals],
        ],
        contradictions=[],
        baseline_version_id=baseline_row.id,
        algorithm_version=ALGORITHM_VERSION,
    )
    db.add(composite)
    db.flush()
    change_signals.append(composite)

    overall_status = "completed" if composite_band != "insufficient_data" or eligible_axes else "insufficient_data"
    if composite_band == "insufficient_data" and not eligible_axes:
        overall_status = "insufficient_data"
    elif any(cs.band != "insufficient_data" for cs in change_signals if cs.feature != "structural_composite"):
        overall_status = "completed"
    elif eligible_axes and any(fv.value.get("n", 0) > 0 for fv in feature_values):
        overall_status = "completed"
    else:
        overall_status = "insufficient_data"

    db.commit()
    for row in (baseline_row, *feature_values, *change_signals):
        db.refresh(row)

    return CanonicalAnalyticsResult(
        status=overall_status,
        correlation_id=corr,
        feature_values=feature_values,
        baseline_version=baseline_row,
        change_signals=change_signals,
        feature_keys=feature_keys,
        detail={
            "baseline_eligible_axes": eligible_axes,
            "composite_band": composite_band,
            "z_scores": z_scores,
            "correlation_id": str(corr),
        },
    )


def refresh_trajectory(db: Session, user_id) -> bool:
    """Recompute this person's canonical baseline and change signals.

    A failure here must not discard the self-report or skip deterministic
    safety. ChangeSignal stays a longitudinal comparison, not a risk level.
    """
    try:
        run_canonical_analytics(db, user_id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Canonical trajectory refresh failed (%s); the self-report and deterministic safety continue.",
            type(exc).__name__,
        )
        db.rollback()
        return False
