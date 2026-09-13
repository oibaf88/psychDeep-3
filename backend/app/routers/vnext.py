"""Contract-first vNext API facade.

These endpoints are additive. Legacy endpoints remain available while the
frontend migrates, so no historical data is reinterpreted or made unreadable.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RiskAssessment, User
from app.models_vnext import BaselineVersion, ChangeSignal, InterventionEvent, Observation
from app.security import get_current_user, require_patient
from app.services import conversation, risk_engine
from app.services.consent import CORE_PROCESSING, is_granted
from app.services.deterministic_safety_text import materialize_user_declaration
from app.services.model_gateway import APPROVED_ALIASES, ModelUnavailable, get_model_gateway
from app.services.timeline import build_patient_timeline

router = APIRouter(prefix="/api/v1", tags=["vnext"])


class ObservationIn(BaseModel):
    type: str = Field(min_length=1, max_length=96)
    value: Any
    unit: str | None = Field(default=None, max_length=48)
    source: str = Field(default="self_report", max_length=64)
    occurred_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=64)
    quality: dict[str, Any] = Field(default_factory=dict)


class SupportIn(BaseModel):
    message: str = Field(min_length=1, max_length=12000)


class FeedbackIn(BaseModel):
    action_id: str = Field(min_length=1, max_length=96)
    state: str = Field(pattern="^(accepted|rejected|postponed|completed)$")
    usefulness: int | None = Field(default=None, ge=1, le=5)
    reason: str | None = Field(default=None, max_length=2000)


def _latest_risk(db: Session, user_id) -> RiskAssessment | None:
    return (
        db.query(RiskAssessment)
        .filter(RiskAssessment.user_id == user_id)
        .order_by(RiskAssessment.created_at.desc())
        .first()
    )


@router.post("/observations", status_code=201)
def create_observation(
    payload: ObservationIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_patient),
):
    if not is_granted(db, user.id, CORE_PROCESSING):
        raise HTTPException(status_code=403, detail="core processing consent is required")
    occurred_at = payload.occurred_at or datetime.now(timezone.utc)
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    row = Observation(
        user_id=user.id,
        source=payload.source,
        type=payload.type,
        value={"value": payload.value},
        unit=payload.unit,
        occurred_at=occurred_at.astimezone(timezone.utc),
        timezone=payload.timezone,
        quality=payload.quality,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "type": row.type,
        "source": row.source,
        "occurred_at": row.occurred_at,
        "received_at": row.received_at,
        "quality": row.quality,
    }


@router.get("/state")
def current_state(db: Session = Depends(get_db), user: User = Depends(require_patient)):
    recent = (
        db.query(Observation)
        .filter(Observation.user_id == user.id)
        .order_by(Observation.occurred_at.desc())
        .limit(20)
        .all()
    )
    risk = _latest_risk(db, user.id)
    latest_by_type: dict[str, dict[str, Any]] = {}
    for row in recent:
        latest_by_type.setdefault(
            row.type,
            {
                "observation_id": str(row.id),
                "value": row.value,
                "occurred_at": row.occurred_at,
                "quality": row.quality,
            },
        )
    expected = {"mood", "craving", "sleep_hours", "self_efficacy"}
    return {
        "latest": latest_by_type,
        "missing": sorted(expected - set(latest_by_type)),
        "safety": {
            "alert_level": risk.alert_level if risk else None,
            "assessment_id": str(risk.id) if risk else None,
            "model_version": risk.model_version if risk else None,
            "correlation_id": str(risk.correlation_id) if risk and risk.correlation_id else None,
        },
        "limits": ["La ausencia de una señal no demuestra ausencia de riesgo."],
    }


@router.get("/baselines/current")
def current_baseline(db: Session = Depends(get_db), user: User = Depends(require_patient)):
    row = (
        db.query(BaselineVersion)
        .filter(BaselineVersion.user_id == user.id, BaselineVersion.status.in_(["active", "provisional", "frozen"]))
        .order_by(BaselineVersion.created_at.desc())
        .first()
    )
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


@router.get("/changes")
def changes(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_patient),
):
    rows = (
        db.query(ChangeSignal)
        .filter(ChangeSignal.user_id == user.id)
        .order_by(ChangeSignal.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
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
        for row in rows
    ]


@router.post("/analytics/run")
def run_analytics(db: Session = Depends(get_db), user: User = Depends(require_patient)):
    # The legacy v1.4 risk engine already computes its structural inputs from
    # cloud data and is deterministic. vNext keeps this as a compatibility
    # bridge while feature/baseline pipelines migrate to canonical tables.
    assessment = risk_engine.run_and_persist(db, user.id)
    return {
        "status": "completed",
        "correlation_id": str(assessment.correlation_id) if assessment.correlation_id else None,
        "risk_assessment_id": str(assessment.id),
        "risk_engine_version": assessment.model_version,
    }


@router.post("/safety/evaluate")
def evaluate_safety(db: Session = Depends(get_db), user: User = Depends(require_patient)):
    assessment = risk_engine.run_and_persist(db, user.id)
    return {
        "assessment_id": str(assessment.id),
        "alert_level": assessment.alert_level,
        "triggering_rules": assessment.triggering_rules,
        "calculation_trace": assessment.calculation_trace,
        "model_version": assessment.model_version,
        "correlation_id": str(assessment.correlation_id) if assessment.correlation_id else None,
    }


@router.post("/support/respond")
def support_respond(payload: SupportIn, db: Session = Depends(get_db), user: User = Depends(require_patient)):
    materialize_user_declaration(db, user.id, payload.message)
    result = conversation.get_reply(db, user, payload.message)
    return {
        "mode": result["ui_mode"],
        "summary": result["reply"],
        "resources": result.get("resources"),
        "correlation_id": str(result["correlation_id"]),
        "limits": ["No sustituye una valoración clínica."],
    }


@router.get("/review/weekly")
def weekly_review(db: Session = Depends(get_db), user: User = Depends(require_patient)):
    timeline = build_patient_timeline(db, user.id, 7)
    risk = _latest_risk(db, user.id)
    return {
        "window_days": 7,
        "timeline": timeline,
        "safety": {
            "alert_level": risk.alert_level if risk else None,
            "assessment_id": str(risk.id) if risk else None,
        },
        "questions_for_review": [
            "¿Qué cambió respecto a tus días habituales?",
            "¿Qué pareció protegerte o ayudarte?",
            "¿Hay contexto que explique algún cambio?",
        ],
    }


@router.get("/model/deployments/status")
def model_status(user: User = Depends(get_current_user)):
    # No URL, credential reference or secret is included in the response.
    active = get_model_gateway()
    active_status = active.health()
    configured = []
    for alias in sorted(APPROVED_ALIASES):
        try:
            deployment = get_model_gateway(alias).deployment()
        except ModelUnavailable:
            continue
        configured.append(deployment.public_dict())
    return {"active": active_status, "deployments": configured}


@router.post("/feedback", status_code=201)
def feedback(payload: FeedbackIn, db: Session = Depends(get_db), user: User = Depends(require_patient)):
    row = InterventionEvent(
        user_id=user.id,
        action_id=payload.action_id,
        state=payload.state,
        reason=payload.reason,
        authority="user_feedback",
        usefulness=payload.usefulness,
        source="patient",
        acted_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "state": row.state, "usefulness": row.usefulness}
