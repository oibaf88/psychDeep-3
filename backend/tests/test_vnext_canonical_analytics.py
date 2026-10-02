"""Canonical analytics path: Observation -> FeatureValue -> BaselineVersion -> ChangeSignal.

Engineering reproducibility tests — not clinical validation of thresholds.
"""
from __future__ import annotations

import json
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Import path creates the default engine; point it at sqlite before first import.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Consent, RiskAssessment, User
from app.models_vnext import (
    BaselineVersion,
    ChangeSignal,
    FeatureDefinition,
    FeatureValue,
    Observation,
)
from app.routers.vnext import current_state, run_analytics
from app.services import canonical_analytics
from app.services.canonical_analytics import ALGORITHM_VERSION, run_canonical_analytics


NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)


def _add_observation(db: Session, user_id, obs_type: str, value: float, occurred_at: datetime) -> Observation:
    row = Observation(
        user_id=user_id,
        source="self_report",
        type=obs_type,
        value={"value": value},
        unit="hours" if obs_type == "sleep_hours" else "0-10",
        occurred_at=occurred_at,
        quality={"test": True},
    )
    db.add(row)
    db.flush()
    return row


def _seed_days(db: Session, user_id, *, days: int, start_offset_days: int, values: dict[str, float]):
    """Write one observation per type per day for `days` consecutive days."""
    for day in range(days):
        when = NOW - timedelta(days=start_offset_days - day)
        for obs_type, value in values.items():
            _add_observation(db, user_id, obs_type, value, when)
    db.commit()


class CanonicalAnalyticsServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # Keep FK checks off so optional consent_id FKs do not require full prod schema.
        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

        Base.metadata.create_all(
            bind=self.engine,
            tables=[
                User.__table__,
                Consent.__table__,
                Observation.__table__,
                FeatureDefinition.__table__,
                FeatureValue.__table__,
                BaselineVersion.__table__,
                ChangeSignal.__table__,
            ],
        )
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.user = User(
            id=uuid.uuid4(),
            email=f"patient-{uuid.uuid4().hex[:8]}@example.test",
            display_name="Test Patient",
            hashed_password="hashed",
            role="patient",
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_enough_observations_persist_feature_baseline_and_change_signals(self):
        # 14 baseline-window days of stable mid-range values + recent mild drift.
        _seed_days(
            self.db,
            self.user.id,
            days=14,
            start_offset_days=20,
            values={"mood": 5.0, "craving": 4.0, "sleep_hours": 7.0, "self_efficacy": 6.0},
        )
        _seed_days(
            self.db,
            self.user.id,
            days=5,
            start_offset_days=5,
            values={"mood": 3.0, "craving": 7.0, "sleep_hours": 5.0, "self_efficacy": 3.0},
        )

        result = run_canonical_analytics(self.db, self.user.id, now=NOW)

        self.assertEqual(result.algorithm_version, ALGORITHM_VERSION)
        self.assertIsNotNone(result.baseline_version)
        self.assertIn(result.baseline_version.status, ("active", "provisional"))
        self.assertEqual(len(result.feature_values), 4)
        self.assertEqual(set(result.feature_keys), {"mood", "craving", "sleep_hours", "self_efficacy"})
        self.assertGreaterEqual(len(result.change_signals), 5)  # 4 features + composite

        self.assertEqual(self.db.query(FeatureValue).count(), 4)
        self.assertEqual(self.db.query(BaselineVersion).filter(BaselineVersion.status != "superseded").count(), 1)
        self.assertGreaterEqual(self.db.query(ChangeSignal).count(), 5)

        composite = next(cs for cs in result.change_signals if cs.feature == "structural_composite")
        self.assertIn(composite.band, ("stable", "transition", "unstable", "insufficient_data"))
        self.assertEqual(composite.algorithm_version, ALGORITHM_VERSION)
        self.assertEqual(composite.baseline_version_id, result.baseline_version.id)

        response = result.to_response()
        self.assertNotIn("risk_assessment_id", response)
        self.assertIn("correlation_id", response)
        self.assertIn("change_signals", response)
        self.assertIn("baseline_version", response)
        self.assertIn("feature_keys", response)

    def test_reproducible_bands_and_algorithm_version_for_fixed_timestamps(self):
        _seed_days(
            self.db,
            self.user.id,
            days=10,
            start_offset_days=18,
            values={"mood": 5.0, "craving": 5.0, "sleep_hours": 7.0, "self_efficacy": 5.0},
        )
        _seed_days(
            self.db,
            self.user.id,
            days=4,
            start_offset_days=4,
            values={"mood": 5.0, "craving": 5.0, "sleep_hours": 7.0, "self_efficacy": 5.0},
        )

        first = run_canonical_analytics(self.db, self.user.id, now=NOW)
        first_bands = {cs.feature: (cs.band, cs.change_value) for cs in first.change_signals}
        first_means = {fv.feature_key: fv.value.get("mean") for fv in first.feature_values}

        second = run_canonical_analytics(self.db, self.user.id, now=NOW)
        second_bands = {cs.feature: (cs.band, cs.change_value) for cs in second.change_signals}
        second_means = {fv.feature_key: fv.value.get("mean") for fv in second.feature_values}

        self.assertEqual(first.algorithm_version, second.algorithm_version)
        self.assertEqual(first_bands, second_bands)
        self.assertEqual(first_means, second_means)
        # Stable mid values should land on stable when recent matches baseline.
        self.assertEqual(first_bands["structural_composite"][0], "stable")

    def test_insufficient_data_does_not_fabricate_zeros(self):
        # Only two mood points — far below eligibility; other types absent.
        _add_observation(self.db, self.user.id, "mood", 4.0, NOW - timedelta(days=2))
        _add_observation(self.db, self.user.id, "mood", 5.0, NOW - timedelta(days=1))
        self.db.commit()

        result = run_canonical_analytics(self.db, self.user.id, now=NOW)

        self.assertEqual(result.status, "insufficient_data")
        for cs in result.change_signals:
            self.assertEqual(cs.band, "insufficient_data")
            self.assertIsNone(cs.change_value)

        for fv in result.feature_values:
            if fv.feature_key == "mood":
                self.assertNotEqual(fv.value.get("mean"), 0)
                self.assertIsNotNone(fv.value.get("mean"))
            else:
                self.assertTrue(fv.value.get("missing"))
                self.assertIsNone(fv.value.get("mean"))
                self.assertEqual(fv.value.get("n"), 0)

        response = result.to_response()
        self.assertNotIn("risk_assessment_id", response)
        self.assertTrue(all(item["change_value"] is None for item in response["change_signals"]))

    def test_run_analytics_router_uses_canonical_path_not_risk_engine(self):
        from pathlib import Path

        source = Path(__file__).resolve().parents[1].joinpath("app/routers/vnext.py").read_text(encoding="utf-8")
        # Narrow check around analytics/run body: must call canonical analytics,
        # must not call risk_engine inside that handler.
        start = source.index('@router.post("/analytics/run")')
        end = source.index('@router.post("/safety/evaluate")')
        analytics_block = source[start:end]
        self.assertIn("run_canonical_analytics", analytics_block)
        self.assertNotIn("risk_engine.run_and_persist", analytics_block)
        self.assertNotIn("risk_assessment_id", analytics_block)

        # Safety endpoint still owns risk.
        safety_block = source[end : end + 500]
        self.assertIn("risk_engine.run_and_persist", safety_block)

        # GET /state reads canonical rows. It must not run analytics, risk, or a model.
        state_start = source.index('@router.get("/state")')
        state_end = source.index('@router.get("/baselines/current")')
        state_block = source[state_start:state_end]
        self.assertIn('"longitudinal": _longitudinal_state', state_block)
        self.assertNotIn("run_canonical_analytics", state_block)
        self.assertNotIn("risk_engine.run_and_persist", state_block)
        self.assertNotIn("get_model_gateway", state_block)
        self.assertNotIn("conversation.get_reply", state_block)

        # Exercise the service response contract used by the router.
        response = run_canonical_analytics(self.db, self.user.id, now=NOW).to_response()
        self.assertNotIn("risk_assessment_id", response)
        self.assertEqual(response["algorithm_version"], ALGORITHM_VERSION)
        self.assertIn("correlation_id", response)


class CheckInUpdatesTrajectoryTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from app.database import get_db
        from app.main import app
        from app.security import get_current_user

        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.user = User(
            id=uuid.uuid4(),
            email="trajectory@example.com",
            hashed_password="x",
            role="patient",
            display_name="Trajectory",
        )
        self.db.add(self.user)
        self.db.add(Consent(user_id=self.user.id, consent_type="data_processing", granted=True))
        self.db.commit()

        def override_get_db():
            yield self.db

        self.app = app
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def test_one_checkin_refreshes_trajectory_and_still_calculates_risk(self):
        response = self.client.post(
            "/api/v1/checkins",
            json={"mood": 5, "craving": 2, "sleep_hours": 7, "self_efficacy": 6},
        )
        self.assertEqual(response.status_code, 201)
        signals = self.db.query(ChangeSignal).filter(ChangeSignal.user_id == self.user.id).all()
        self.assertTrue(signals)
        self.assertTrue(all(signal.feature != "risk_assessment" for signal in signals))
        self.assertIsNotNone(
            self.db.query(BaselineVersion).filter(BaselineVersion.user_id == self.user.id).first()
        )
        self.assertIsNotNone(
            self.db.query(RiskAssessment).filter(RiskAssessment.user_id == self.user.id).first()
        )

    def test_trajectory_failure_still_stores_the_checkin_and_the_risk(self):
        with patch.object(canonical_analytics, "run_canonical_analytics", side_effect=RuntimeError("trajectory")):
            response = self.client.post(
                "/api/v1/checkins",
                json={"mood": 4, "craving": 3, "sleep_hours": 6, "self_efficacy": 5},
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.db.query(ChangeSignal).count(), 0)
        self.assertIsNotNone(
            self.db.query(RiskAssessment).filter(RiskAssessment.user_id == self.user.id).first()
        )


class MissingIsNotZeroUnitTests(unittest.TestCase):
    def test_finite_number_rejects_none_bool_and_nan(self):
        self.assertIsNone(canonical_analytics._finite_number(None))
        self.assertIsNone(canonical_analytics._finite_number(True))
        self.assertIsNone(canonical_analytics._finite_number(float("nan")))
        self.assertEqual(canonical_analytics._finite_number(3), 3.0)


if __name__ == "__main__":
    unittest.main()
