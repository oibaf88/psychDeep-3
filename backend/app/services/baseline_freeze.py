"""Supervised freeze / release of the canonical personal baseline.

vNext spec 8.2: the personal baseline must be able to be frozen or
recalibrated *with supervision*, so a period the clinician does not want
treated as the person's "new normal" is not absorbed into the reference.

A freeze never edits an existing row. It appends a copy of the current
canonical reference with ``status = "frozen"`` and a ``supervised_freeze``
entry in ``exclusions`` (who, when, why, which row it holds), and marks the
source row ``superseded``. While it is frozen, ``run_canonical_analytics``
compares new observations against that held reference instead of building a
new one. Releasing it marks the frozen row ``retired`` and recomputes the
reference from the normal windows.

This only changes the reference of the canonical ChangeSignal comparison.
It never touches RiskAssessment, the risk engine's structural input, alert
levels or thresholds, and it never calls a model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models_vnext import BaselineVersion
from app.services import audit
from app.services.canonical_analytics import ALGORITHM_VERSION, refresh_trajectory

FREEZE_EXCLUSION_KIND = "supervised_freeze"
FREEZE_REASON_CODE = "reference_held_by_professional"


class BaselineFreezeError(Exception):
    """The requested freeze/release does not apply to the current reference."""


def current_canonical_baseline(db: Session, user_id) -> BaselineVersion | None:
    return (
        db.query(BaselineVersion)
        .filter(
            BaselineVersion.user_id == user_id,
            BaselineVersion.algorithm_version == ALGORITHM_VERSION,
            BaselineVersion.status.in_(["active", "provisional", "frozen"]),
        )
        .order_by(BaselineVersion.created_at.desc())
        .first()
    )


def freeze_record(row: BaselineVersion | None) -> dict[str, Any] | None:
    for entry in (getattr(row, "exclusions", None) or []):
        if isinstance(entry, dict) and entry.get("kind") == FREEZE_EXCLUSION_KIND:
            return entry
    return None


def freeze_baseline(
    db: Session,
    user_id,
    *,
    actor_id,
    actor_role: str,
    reason: str,
    now: datetime | None = None,
) -> BaselineVersion:
    current = current_canonical_baseline(db, user_id)
    if current is None:
        raise BaselineFreezeError("no_canonical_baseline")
    if current.status == "frozen":
        raise BaselineFreezeError("already_frozen")
    if not (current.stats or {}) or current.stability == "insufficient_data":
        # Holding an empty reference would freeze "no comparison" in place.
        raise BaselineFreezeError("insufficient_data")

    current_time = now or datetime.now(timezone.utc)
    frozen_at = current_time.isoformat()
    exclusions = [dict(entry) for entry in (current.exclusions or []) if isinstance(entry, dict)]
    exclusions.append(
        {
            "kind": FREEZE_EXCLUSION_KIND,
            "reason": FREEZE_REASON_CODE,
            "frozen_at": frozen_at,
            "frozen_by": str(actor_id),
            "frozen_by_role": actor_role,
            "note": reason,
            "source_baseline_version_id": str(current.id),
            "excludes": "observations_after_the_reference_window_until_released",
        }
    )
    frozen = BaselineVersion(
        user_id=user_id,
        feature_key=current.feature_key,
        window_start=current.window_start,
        window_end=current.window_end,
        stats=dict(current.stats or {}),
        exclusions=exclusions,
        stability=current.stability,
        data_coverage=current.data_coverage,
        status="frozen",
        algorithm_version=current.algorithm_version,
    )
    current.status = "superseded"
    db.add(frozen)
    db.commit()
    db.refresh(frozen)

    audit.log(
        db,
        actor_id=actor_id,
        actor_role=actor_role,
        action="baseline_frozen",
        entity_type="baseline_version",
        entity_id=frozen.id,
        extra={
            "patient_id": str(user_id),
            "source_baseline_version_id": str(current.id),
            "algorithm_version": frozen.algorithm_version,
        },
    )
    # Re-read the trajectory against the held reference right away, so the
    # current reading cites the frozen row rather than the superseded one.
    refresh_trajectory(db, user_id, now=current_time)
    return frozen


def release_baseline(
    db: Session,
    user_id,
    *,
    actor_id,
    actor_role: str,
    now: datetime | None = None,
) -> BaselineVersion | None:
    current = current_canonical_baseline(db, user_id)
    if current is None or current.status != "frozen":
        raise BaselineFreezeError("not_frozen")
    current.status = "retired"
    db.commit()
    audit.log(
        db,
        actor_id=actor_id,
        actor_role=actor_role,
        action="baseline_released",
        entity_type="baseline_version",
        entity_id=current.id,
        extra={"patient_id": str(user_id), "algorithm_version": current.algorithm_version},
    )
    # Recalibrate: rebuild the reference from the normal windows now.
    refresh_trajectory(db, user_id, now=now)
    return current_canonical_baseline(db, user_id)
