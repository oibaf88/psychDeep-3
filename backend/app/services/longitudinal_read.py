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
from typing import Any

from sqlalchemy.orm import Session

from app.models_vnext import BaselineVersion, ChangeSignal, FeatureValue
from app.services.canonical_analytics import AXIS_FOR_TYPE, MIN_OBS_FOR_BASELINE
from app.services.baseline import STD_FLOORS

READABLE_BASELINE_STATUSES = ("active", "provisional", "frozen")
CHANGE_IS_NOT_RISK = "La ausencia de una señal de cambio no demuestra ausencia de riesgo."


def current_baseline(db: Session, user_id) -> BaselineVersion | None:
    return (
        db.query(BaselineVersion)
        .filter(
            BaselineVersion.user_id == user_id,
            BaselineVersion.status.in_(READABLE_BASELINE_STATUSES),
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
    return {"baseline": baseline_summary(baseline), "changes": changes}


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
        "limits": [CHANGE_IS_NOT_RISK],
    }
