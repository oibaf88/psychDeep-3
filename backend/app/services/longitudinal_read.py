"""Read persisted BaselineVersion and ChangeSignal rows.

This module does not recompute analytics, calculate risk, or call a model.
Missing canonical rows stay ``insufficient_data`` / null. A null change is
never a zero and never an alert level.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models_vnext import BaselineVersion, ChangeSignal

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


def change_signal_summary(row: ChangeSignal) -> dict[str, Any]:
    """ChangeSignal fields only. Unknown change stays null and is not a risk level."""
    return {
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


def _latest_relevant_changes(rows: list[ChangeSignal]) -> list[ChangeSignal]:
    """Newest row per feature. ``rows`` must already be newest-first."""
    latest: dict[str, ChangeSignal] = {}
    for row in rows:
        latest.setdefault(row.feature, row)
    return list(latest.values())


def _state_for(baseline: BaselineVersion | None, rows: list[ChangeSignal]) -> dict[str, Any]:
    return {
        "baseline": baseline_summary(baseline),
        "changes": [change_signal_summary(row) for row in _latest_relevant_changes(rows)],
    }


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

    result: dict[Any, dict[str, Any]] = {}
    for user_id in unique_ids:
        baseline = chosen.get(str(user_id))
        rows = signals_by_baseline.get(str(baseline.id), []) if baseline is not None else []
        result[user_id] = _state_for(baseline, rows)
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
