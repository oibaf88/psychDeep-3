"""Read persisted BaselineVersion, FeatureValue and ChangeSignal rows.

This module does not recompute analytics, calculate risk, or call a model.
Missing canonical rows stay ``insufficient_data`` / null. A null change is
never a zero and never an alert level.

Each per-feature change carries the FeatureValue it cites and the matching
axis of its BaselineVersion, so the explanation "recent versus your own
reference" comes from the canonical rows rather than the legacy baseline.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models_vnext import BaselineVersion, ChangeSignal, FeatureValue
from app.services.canonical_analytics import AXIS_FOR_TYPE, MIN_OBS_FOR_BASELINE
from app.services.baseline import RECENT_WINDOW_DAYS, STD_FLOORS
from app.utils import as_utc

READABLE_BASELINE_STATUSES = ("active", "provisional", "frozen")
CHANGE_IS_NOT_RISK = "La ausencia de una señal de cambio no demuestra ausencia de riesgo."

# Only baselines written by the canonical pipeline describe the person's
# *current* reference. Rows imported from the legacy engine
# (``legacy-baseline-import-v1``) stay in history but have no canonical
# ChangeSignals attached. Reading one as "current" made screens say
# "Sirve como referencia" next to "no hay datos para comparar".
CANONICAL_ALGORITHM_PREFIX = "canonical-"

# A comparison older than its own recent window describes a week that has
# fully rolled over. It is still shown, but flagged as out of date.
STALE_AFTER_DAYS = RECENT_WINDOW_DAYS

CALCULATED_BANDS = ("stable", "transition", "unstable")
FEATURE_UNITS = {"mood": "0-10", "craving": "0-10", "sleep_hours": "h", "self_efficacy": "0-10"}
# Below this absolute difference (in the feature's own unit) the direction is
# reported as "similar". Presentation rounding only, not a clinical threshold.
SIMILAR_DIFFERENCE = 0.05


def current_baseline(db: Session, user_id) -> BaselineVersion | None:
    return (
        db.query(BaselineVersion)
        .filter(
            BaselineVersion.user_id == user_id,
            BaselineVersion.status.in_(READABLE_BASELINE_STATUSES),
            BaselineVersion.algorithm_version.like(f"{CANONICAL_ALGORITHM_PREFIX}%"),
        )
        .order_by(BaselineVersion.created_at.desc())
        .first()
    )


def baseline_summary(row: BaselineVersion | None) -> dict[str, Any]:
    """Personal baseline summary. No row is insufficient_data, not a zero baseline."""
    if row is None:
        return {"status": "insufficient_data", "baseline": None}
    return {
        "status": row.status,
        "baseline": {
            "id": str(row.id),
            "feature": row.feature_key,
            "window": {"start": row.window_start, "end": row.window_end},
            "stats": row.stats,
            "stability": row.stability,
            "data_coverage": row.data_coverage,
            "algorithm_version": row.algorithm_version,
            "exclusions": getattr(row, "exclusions", None) or [],
        },
    }


def cited_feature_value_id(row: ChangeSignal) -> str | None:
    """The FeatureValue a per-feature ChangeSignal compared, from its evidence refs.

    The composite signal cites several FeatureValues and has no single one.
    """
    if row.feature not in AXIS_FOR_TYPE:
        return None
    for ref in row.evidence_refs or []:
        if isinstance(ref, dict) and ref.get("kind") == "feature_value" and ref.get("id"):
            return str(ref["id"])
    return None


def _recomputes(row: ChangeSignal, recent_mean: float, axis_stats: dict[str, Any]) -> bool:
    """Whether the stored change equals the comparison of the two cited rows."""
    axis = AXIS_FOR_TYPE[row.feature]
    effective_std = max(float(axis_stats["std"]), STD_FLOORS[axis])
    expected = round((recent_mean - float(axis_stats["mean"])) / effective_std, 6)
    return abs(expected - float(row.change_value)) <= 1e-6


def feature_evidence(
    row: ChangeSignal,
    feature_value: FeatureValue | None,
    baseline: BaselineVersion | None,
) -> dict[str, Any] | None:
    """Recent FeatureValue and baseline axis cited by one per-feature change.

    Returns None for the composite signal. A missing or foreign FeatureValue,
    or a missing baseline axis, stays null with ``insufficient_data``. Missing
    is never shown as a zero mean.
    """
    if row.feature not in AXIS_FOR_TYPE:
        return None
    axis = AXIS_FOR_TYPE[row.feature]
    if feature_value is not None and (
        str(feature_value.user_id) != str(row.user_id) or feature_value.feature_key != row.feature
    ):
        feature_value = None

    recent = None
    recent_mean = None
    if feature_value is not None:
        payload = feature_value.value if isinstance(feature_value.value, dict) else {}
        recent_mean = payload.get("mean")
        recent = {
            "feature_value_id": str(feature_value.id),
            "mean": recent_mean,
            "n": int(payload.get("n") or 0),
            "missing": recent_mean is None,
            "window": {"start": feature_value.window_start, "end": feature_value.window_end},
            "quality_flags": list(feature_value.quality_flags or []),
            "feature_version": feature_value.feature_version,
            "algorithm_version": feature_value.algorithm_version,
        }

    axis_stats = None
    if baseline is not None and str(row.baseline_version_id) == str(baseline.id):
        candidate = (baseline.stats or {}).get(axis)
        if isinstance(candidate, dict) and candidate.get("mean") is not None:
            axis_stats = candidate
    reference = (
        None
        if axis_stats is None
        else {
            "baseline_version_id": str(baseline.id),
            "mean": axis_stats.get("mean"),
            "std": axis_stats.get("std"),
            "n": int(axis_stats.get("n") or 0),
            "eligible": int(axis_stats.get("n") or 0) >= MIN_OBS_FOR_BASELINE,
        }
    )

    reproduced = None
    if row.change_value is not None and recent_mean is not None and axis_stats is not None:
        reproduced = _recomputes(row, float(recent_mean), axis_stats)

    available = (
        recent is not None
        and not recent["missing"]
        and reference is not None
        and reference["eligible"]
    )
    return {
        "status": "available" if available else "insufficient_data",
        "axis": axis,
        "inverted": axis != row.feature,
        "recent": recent,
        "reference": reference,
        "reproduced_from_rows": reproduced,
        "display": _display(row, recent_mean, axis_stats if reference and reference["eligible"] else None),
    }


def _natural(feature: str, axis_value: Any) -> float | None:
    """Undo the internal craving inversion so readers see the declared scale."""
    if axis_value is None:
        return None
    try:
        value = float(axis_value)
    except (TypeError, ValueError):
        return None
    return round(10.0 - value if feature == "craving" else value, 2)


def _display(row: ChangeSignal, recent_mean: Any, axis_stats: dict[str, Any] | None) -> dict[str, Any]:
    """The comparison in the person's own scale: values, difference and direction.

    ``recent_value`` / ``reference_value`` are means on the declared scale
    (craving is NOT inverted here). ``z`` keeps the declared direction too: a
    positive z means the recent mean is higher than the reference. Anything
    unknown stays null; nothing becomes a zero.
    """
    recent_value = _natural(row.feature, recent_mean)
    reference_value = _natural(row.feature, axis_stats.get("mean")) if axis_stats else None
    difference = None
    direction = None
    if recent_value is not None and reference_value is not None:
        difference = round(recent_value - reference_value, 2)
        if abs(difference) < SIMILAR_DIFFERENCE:
            direction = "similar"
        else:
            direction = "higher" if difference > 0 else "lower"
    z = None
    if row.change_value is not None and row.band in CALCULATED_BANDS:
        z = round(-float(row.change_value) if row.feature == "craving" else float(row.change_value), 2)
    return {
        "unit": FEATURE_UNITS.get(row.feature),
        "recent_value": recent_value,
        "reference_value": reference_value,
        "difference": difference,
        "direction": direction,
        "z": z,
    }


_NOT_READ: Any = object()


def change_signal_summary(row: ChangeSignal, evidence: Any = _NOT_READ) -> dict[str, Any]:
    """ChangeSignal fields only. Unknown change stays null and is not a risk level.

    ``evidence`` is added only when the caller read the cited FeatureValue.
    """
    summary = {
        "signal_id": str(row.id),
        "feature": row.feature,
        "window": {"start": row.window_start, "end": row.window_end},
        "change": row.change_value,
        "band": row.band,
        "uncertainty": row.uncertainty,
        "evidence_refs": row.evidence_refs,
        "contradictions": row.contradictions,
        "baseline_version": str(row.baseline_version_id) if row.baseline_version_id else None,
        "algorithm_version": row.algorithm_version,
    }
    if evidence is not _NOT_READ:
        summary["evidence"] = evidence
    return summary


def _latest_relevant_changes(rows: list[ChangeSignal]) -> list[ChangeSignal]:
    """Newest row per feature. ``rows`` must already be newest-first."""
    latest: dict[str, ChangeSignal] = {}
    for row in rows:
        latest.setdefault(row.feature, row)
    return list(latest.values())


def _count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def comparison_summary(
    baseline: BaselineVersion | None,
    rows: list[ChangeSignal],
    now: datetime | None = None,
) -> dict[str, Any]:
    """One status for the whole comparison, so every screen tells the same story.

    ``status`` is one of:
    - ``not_computed``: no canonical baseline/comparison has been run yet;
    - ``insufficient_reference``: the personal reference does not have enough
      observations for any area;
    - ``no_recent_data``: the reference exists but there are no recent
      observations to compare;
    - ``partial``: some areas are compared, others are not (listed with reason);
    - ``calculated``: every area is compared.
    This is a description of data availability, never a risk level.
    """
    current = as_utc(now) if now is not None else datetime.now(timezone.utc)
    per_feature = [row for row in rows if row.feature in AXIS_FOR_TYPE]
    calculated = [
        row.feature
        for row in per_feature
        if row.change_value is not None and row.band in CALCULATED_BANDS
    ]
    pending = []
    for row in per_feature:
        if row.feature in calculated:
            continue
        uncertainty = row.uncertainty if isinstance(row.uncertainty, dict) else {}
        baseline_n = _count(uncertainty.get("baseline_n"))
        recent_n = _count(uncertainty.get("recent_n"))
        reference_short = baseline_n < MIN_OBS_FOR_BASELINE
        recent_missing = recent_n == 0
        reason = "both" if reference_short and recent_missing else "reference" if reference_short else "recent"
        pending.append(
            {
                "feature": row.feature,
                "reason": reason,
                "baseline_n": baseline_n,
                "recent_n": recent_n,
                "minimum_reference_n": MIN_OBS_FOR_BASELINE,
            }
        )

    if baseline is None or not per_feature:
        status = "not_computed"
    elif calculated and not pending:
        status = "calculated"
    elif calculated:
        status = "partial"
    elif all(item["reason"] == "recent" for item in pending):
        status = "no_recent_data"
    else:
        status = "insufficient_reference"

    window_ends = [as_utc(row.window_end) for row in per_feature if row.window_end is not None]
    window_starts = [as_utc(row.window_start) for row in per_feature if row.window_start is not None]
    computed_at = max(window_ends) if window_ends else None
    is_stale = bool(computed_at is not None and current - computed_at > timedelta(days=STALE_AFTER_DAYS))
    return {
        "status": status,
        "calculated_features": calculated,
        "pending_features": pending,
        "computed_at": computed_at,
        "recent_window": {
            "start": min(window_starts) if window_starts else None,
            "end": computed_at,
        },
        "reference_window": {
            "start": as_utc(baseline.window_start) if baseline is not None and baseline.window_start else None,
            "end": as_utc(baseline.window_end) if baseline is not None and baseline.window_end else None,
        },
        "algorithm_version": baseline.algorithm_version if baseline is not None else None,
        "is_stale": is_stale,
        "stale_after_days": STALE_AFTER_DAYS,
        "minimum_reference_n": MIN_OBS_FOR_BASELINE,
    }


def _state_for(
    baseline: BaselineVersion | None,
    rows: list[ChangeSignal],
    feature_values: dict[str, FeatureValue],
) -> dict[str, Any]:
    changes = []
    for row in rows:
        cited = cited_feature_value_id(row)
        evidence = feature_evidence(row, feature_values.get(cited) if cited else None, baseline)
        changes.append(change_signal_summary(row, evidence))
    return {
        "baseline": baseline_summary(baseline),
        "changes": changes,
        "summary": comparison_summary(baseline, rows),
    }


def _cited_feature_values(db: Session, signals: list[ChangeSignal]) -> dict[str, FeatureValue]:
    ids = []
    for signal in signals:
        cited = cited_feature_value_id(signal)
        if cited is None:
            continue
        try:
            ids.append(uuid.UUID(cited))
        except ValueError:
            continue
    if not ids:
        return {}
    rows = db.query(FeatureValue).filter(FeatureValue.id.in_(list(dict.fromkeys(ids)))).all()
    return {str(row.id): row for row in rows}


def longitudinal_states(db: Session, user_ids: list) -> dict[Any, dict[str, Any]]:
    """Same read as ``longitudinal_state``, for several people. Does not recompute."""
    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        return {}

    baselines = (
        db.query(BaselineVersion)
        .filter(
            BaselineVersion.user_id.in_(unique_ids),
            BaselineVersion.status.in_(READABLE_BASELINE_STATUSES),
            BaselineVersion.algorithm_version.like(f"{CANONICAL_ALGORITHM_PREFIX}%"),
        )
        .order_by(BaselineVersion.created_at.desc())
        .all()
    )
    chosen: dict[str, BaselineVersion] = {}
    for row in baselines:
        chosen.setdefault(str(row.user_id), row)

    signals_by_baseline: dict[str, list[ChangeSignal]] = {}
    baseline_ids = [row.id for row in chosen.values()]
    if baseline_ids:
        signals = (
            db.query(ChangeSignal)
            .filter(ChangeSignal.baseline_version_id.in_(baseline_ids))
            .order_by(ChangeSignal.created_at.desc(), ChangeSignal.feature.asc())
            .all()
        )
        allowed = {str(row.user_id): str(row.id) for row in chosen.values()}
        for signal in signals:
            if allowed.get(str(signal.user_id)) != str(signal.baseline_version_id):
                continue
            signals_by_baseline.setdefault(str(signal.baseline_version_id), []).append(signal)

    latest_by_user: dict[Any, list[ChangeSignal]] = {}
    for user_id in unique_ids:
        baseline = chosen.get(str(user_id))
        rows = signals_by_baseline.get(str(baseline.id), []) if baseline is not None else []
        latest_by_user[user_id] = _latest_relevant_changes(rows)
    feature_values = _cited_feature_values(
        db, [signal for rows in latest_by_user.values() for signal in rows]
    )

    result: dict[Any, dict[str, Any]] = {}
    for user_id in unique_ids:
        result[user_id] = _state_for(chosen.get(str(user_id)), latest_by_user[user_id], feature_values)
    return result


def longitudinal_state(db: Session, user_id) -> dict[str, Any]:
    """Read persisted BaselineVersion and ChangeSignal rows. Does not recompute."""
    return longitudinal_states(db, [user_id])[user_id]


def for_clinical_reader(state: dict[str, Any]) -> dict[str, Any]:
    """Copy a longitudinal read and state the limit that separates it from risk.

    The baseline and change rows are unchanged. Nothing here becomes an alert level.
    """
    return {
        "baseline": state["baseline"],
        "changes": list(state["changes"]),
        "summary": state.get("summary"),
        "limits": [CHANGE_IS_NOT_RISK],
    }
