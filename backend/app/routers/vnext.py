"""Contract-first vNext API facade.

These endpoints are additive. Legacy endpoints remain available while the
frontend migrates, so no historical data is reinterpreted or made unreadable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models_vnext import BaselineVersion, ChangeSignal, InterventionEvent, Observation
from app.security import get_current_user, require_patient
from app.services import conversation, risk_engine
from app.services.canonical_analytics import run_canonical_analytics
from app.services.change_signal_embeddings import embed_change_signals
from app.services.longitudinal_read import (
    baseline_summary as _baseline_summary,
    change_signal_summary as _change_signal_summary,
    current_baseline as _current_baseline,
    for_clinical_reader as _for_clinical_reader,
    longitudinal_state as _longitudinal_state,
)
from app.services.consent import CORE_PROCESSING, is_granted, require_granted
from app.services.deterministic_safety_text import materialize_user_declaration
from app.services.model_gateway import APPROVED_ALIASES, ModelUnavailable, get_model_gateway
from app.services.timeline import build_patient_timeline

router = APIRouter(prefix="/api/v1", tags=["vnext"])
