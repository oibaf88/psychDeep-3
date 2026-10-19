"""Deep learning proposal for a single-patient time-aware change model.

This is an opt-in module. It does not make the app depend on PyTorch or on a
shared worker. When the ML libraries are unavailable, the app keeps the
deterministic fallback in ``sequence_model.py`` and never writes
``RiskAssessment.alert_level`` from the model.

Design (patient is the only dataset):
- No cross-patient cohorts, no transfer learning, no images, no EHR.
- Input: the app's own check-ins / diary / chat / confirmed facts.
- Output: ``ChangeSignalDraft`` (effect, confidence, explanation, fingerprint).
- ``alert_level`` is written only by the deterministic engine.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

logger = logging.getLogger("psychdeep.sequence_dlearning")

TRUSTY_TF = ("torch", "tensorflow", "sklearn")
_MISSING: list[str] = []
for _name in TRUSTY_TF:
    try:
        __import__(_name)
    except ImportError:  # pragma: no cover - depends on deployment env
        _MISSING.append(_name)

_has_ml = len(_MISSING) == 0

if not _has_ml:
    logger.warning(
        "ML imports unavailable (%s); sequence model runs the deterministic fallback",
        ", ".join(_MISSING),
    )


# ---------------------------------------------------------------------------
# Config: versioned hyperparameters for one patient model.
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "algorithm_version": "patient-sequence-dl-v1",
    "prompt_version": "patient-sequence-2026-10",
    "model_type": "patient_sequence_mlp",
    "architecture": {
        "input_dim": 12,
        "hidden": [32, 16],
        "dropout": 0.15,
    },
    "training": {
        "window_days": 365.0,
        "min_points": 3,
        "epochs": 64,
        "batch_size": 4,
        "learning_rate": 1e-3,
        "early_stop_patience": 6,
        "random_seed": 7,
    },
    "norms": {
        "min_effect": -1.0,
        "max_effect": 1.0,
        "min_confidence": 0.0,
    },
    "consent": ["linguistic_analysis"],
    "source_refs": "app-only",
}


def config_path() -> str:
    """Optional file path for a patient's override. Empty means defaults."""
    return os.environ.get("SEQUENCE_DLEARNING_CONFIG", "")


def load_config() -> dict:
    """Reads the versioned config without changing the defaults."""
    path = config_path()
    if not path:
        return dict(DEFAULT_CONFIG)
    try:
        import json

        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # pragma: no cover - fallback to defaults
        logger.warning("sequence_dlearning config unreadable (%s); using defaults", exc)
        return dict(DEFAULT_CONFIG)


def requires_ml() -> bool:
    return _has_ml


def requires_consent(
    db,
    user_id: str,
    purpose: str = "linguistic_analysis",
    *,
    required_until: str | None = None,
) -> bool:
    """Fast-check that a patient granted the exact consent and it is still valid.

    This is the execution-time gate for the optional ML module. In a production
    deployment it MUST be called before any optional model run. It only reads
    current consent rows; the deterministic engine remains the sole writer of
    ``RiskAssessment.alert_level``.
    """
    if not requires_ml():
        return False
    try:
        from app.services.consent import is_granted

        granted = is_granted(db, user_id, purpose)
        if not granted:
            return False
        # Check `valid_until` if the consent row exposes that column. If the
        # schema does not carry `valid_until`, consent is treated as open.
        try:
            from app.models import Consent  # type: ignore

            row = db.query(Consent).filter(Consent.user_id == user_id, Consent.consent_type == purpose).first()
            if row is not None and getattr(row, "valid_until", None) and required_until:
                return row.valid_until >= required_until
        except Exception:
            pass
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Proposal: architecture, data contracts, governance and this module's own
# fallback behaviour. The code below is the deployable part; training/eval
# pipelines live in the ML infra repo and are not imported here.
# ---------------------------------------------------------------------------
# Proposed model:
#   patient_sequence_mlp - a small multi-layer perceptron over normalised
#   time-aware features (age_delta, time_since_last_event, recent_activity,
#   spacing_entropy, last_effect) plus optional textual embeddings from the
#   patient's own diary/chat. Dropout and early stopping mitigate small data.
#
# Training capacity:
#   epochs: 64, batch_size: 4, lr: 1e-3, early_stop_patience: 6.
#
# Governance:
#   algorithm_version/prompt_version per patient; consent check at startup;
#   source_digest/hash of patient events; metrics logged but never used for
#   ``alert_level``.
# ---------------------------------------------------------------------------
