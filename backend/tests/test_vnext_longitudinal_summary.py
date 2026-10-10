"""One comparison status and the declared-scale values every screen renders.

These cover the three defects the product owner reported:
1. a "datos suficientes" status with no values behind it;
2. (chart) — covered in the frontend suite;
3. "hay referencia" above "no hay datos para comparar" on the same page.
Engineering tests only; they do not validate clinical thresholds and never
touch RiskAssessment.
"""
from __future__ import annotations

import os
import unittest
import uuid
from datetime import timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Consent, User
from app.models_vnext import BaselineVersion, ChangeSignal, FeatureDefinition, FeatureValue, Observation
from app.schemas import LongitudinalStateOut
from app.services.canonical_analytics import run_canonical_analytics
from app.services.longitudinal_read import (
    comparison_summary,
    current_baseline,
    for_clinical_reader,
    longitudinal_state,
)
from tests.test_vnext_canonical_analytics import NOW, _add_observation, _seed_days

STABLE = {"mood": 6.0, "craving": 3.0, "sleep_hours": 7.0, "self_efficacy": 6.0}
WORSE = {"mood": 3.0, "craving": 7.0, "sleep_hours": 5.0, "self_efficacy": 3.0}


class LongitudinalSummaryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

        Base.metadata.create_all(
            bind=self.engine,
            tables=[User.__table__, Consent.__table__, Observation.__table__, FeatureDefinition.__table__,
                    FeatureValue.__table__, BaselineVersion.__table__, ChangeSignal.__table__],
        )
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.user = User(id=uuid.uuid4(), email=f"p-{uuid.uuid4().hex[:8]}@example.test",
                         display_name="P", hashed_password="x", role="patient")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _reference_and_recent(self, recent=WORSE):
        _seed_days(self.db, self.user.id, days=14, start_offset_days=21, values=STABLE)
        if recent is not None:
            _seed_days(self.db, self.user.id, days=5, start_offset_days=5, values=recent)

    def test_calculated_comparison_carries_declared_scale_values_and_direction(self):
        self._reference_and_recent()
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        state = longitudinal_state(self.db, self.user.id)

        self.assertEqual(state["summary"]["status"], "calculated")
        self.assertEqual(state["summary"]["pending_features"], [])
        changes = {row["feature"]: row for row in state["changes"]}

        mood = changes["mood"]["evidence"]["display"]
        self.assertEqual((mood["recent_value"], mood["reference_value"]), (3.0, 6.0))
        self.assertEqual(mood["difference"], -3.0)
        self.assertEqual(mood["direction"], "lower")
        self.assertLess(mood["z"], 0)

        # Craving is stored inverted internally. Readers must see the declared
        # scale: craving went UP from 3 to 7, and z is positive.
        craving = changes["craving"]["evidence"]["display"]
        self.assertEqual((craving["recent_value"], craving["reference_value"]), (7.0, 3.0))
        self.assertEqual(craving["direction"], "higher")
        self.assertGreater(craving["z"], 0)
        self.assertEqual(changes["sleep_hours"]["evidence"]["display"]["unit"], "h")
        self.assertIsNone(changes["structural_composite"]["evidence"])

    def test_reference_without_recent_observations_is_no_recent_data_not_insufficient(self):
        self._reference_and_recent(recent=None)
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        summary = longitudinal_state(self.db, self.user.id)["summary"]

        self.assertEqual(summary["status"], "no_recent_data")
        self.assertEqual({item["reason"] for item in summary["pending_features"]}, {"recent"})
        self.assertTrue(all(item["baseline_n"] >= 5 for item in summary["pending_features"]))

    def test_too_short_history_is_insufficient_reference_with_counts(self):
        _seed_days(self.db, self.user.id, days=4, start_offset_days=4, values=STABLE)
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        summary = longitudinal_state(self.db, self.user.id)["summary"]

        self.assertEqual(summary["status"], "insufficient_reference")
        for item in summary["pending_features"]:
            self.assertEqual(item["reason"], "reference")
            self.assertEqual(item["baseline_n"], 0)
            self.assertEqual(item["recent_n"], 4)
            self.assertEqual(item["minimum_reference_n"], 5)

    def test_partial_comparison_names_the_missing_area(self):
        self._reference_and_recent()
        for day in range(3):
            _add_observation(self.db, self.user.id, "mood", 5.0, NOW - timedelta(days=day))
        self.db.query(Observation).filter(Observation.type == "sleep_hours",
                                          Observation.occurred_at >= NOW - timedelta(days=6)).delete()
        self.db.commit()
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        summary = longitudinal_state(self.db, self.user.id)["summary"]

        self.assertEqual(summary["status"], "partial")
        self.assertEqual([item["feature"] for item in summary["pending_features"]], ["sleep_hours"])
        self.assertEqual(summary["pending_features"][0]["reason"], "recent")

    def test_legacy_imported_baseline_is_not_read_as_the_current_reference(self):
        self.db.add(BaselineVersion(user_id=self.user.id, feature_key=None,
                                    window_start=NOW - timedelta(days=40), window_end=NOW - timedelta(days=19),
                                    stats={"mood": {"mean": 6.0, "std": 1.0, "n": 21}}, exclusions=[],
                                    stability="legacy_unknown", status="active",
                                    algorithm_version="legacy-baseline-import-v1"))
        self.db.commit()

        self.assertIsNone(current_baseline(self.db, self.user.id))
        state = longitudinal_state(self.db, self.user.id)
        self.assertEqual(state["baseline"]["status"], "insufficient_data")
        self.assertEqual(state["summary"]["status"], "not_computed")
        # The legacy row is still there; it is history, not deleted.
        self.assertEqual(self.db.query(BaselineVersion).count(), 1)

    def test_stale_comparison_is_flagged_with_its_date(self):
        self._reference_and_recent()
        result = run_canonical_analytics(self.db, self.user.id, now=NOW)
        rows = [row for row in result.change_signals]

        fresh = comparison_summary(result.baseline_version, rows, now=NOW + timedelta(days=2))
        stale = comparison_summary(result.baseline_version, rows, now=NOW + timedelta(days=9))
        self.assertFalse(fresh["is_stale"])
        self.assertTrue(stale["is_stale"])
        self.assertEqual(stale["computed_at"], NOW)

    def test_professional_schema_keeps_evidence_and_summary(self):
        self._reference_and_recent()
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        payload = LongitudinalStateOut.model_validate(
            for_clinical_reader(longitudinal_state(self.db, self.user.id))
        ).model_dump(mode="json")

        self.assertEqual(payload["summary"]["status"], "calculated")
        mood = next(row for row in payload["changes"] if row["feature"] == "mood")
        self.assertEqual(mood["evidence"]["display"]["direction"], "lower")


if __name__ == "__main__":
    unittest.main()
