"""Canonical baseline lifecycle: the comparison window is excluded from the reference.

A ChangeSignal compares the recent window against the personal baseline. If the
baseline also contained that recent window, a relevant episode would be absorbed
into its own reference and pulled toward "stable". These are engineering
reproducibility tests, not clinical validation of thresholds.
"""
from __future__ import annotations

import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Consent, User
from app.models_vnext import (
    BaselineVersion,
    ChangeSignal,
    FeatureDefinition,
    FeatureValue,
    Observation,
)
from app.services.baseline import BASELINE_WINDOW_DAYS, RECENT_WINDOW_DAYS
from app.services.canonical_analytics import (
    ALGORITHM_VERSION,
    baseline_reference_window,
    run_canonical_analytics,
)
from app.schemas import LongitudinalBaselineOut
from app.services.longitudinal_read import baseline_summary, longitudinal_state

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
STABLE = {"mood": 5.0, "craving": 4.0, "sleep_hours": 7.0, "self_efficacy": 6.0}
SHIFTED = {"mood": 2.0, "craving": 8.0, "sleep_hours": 4.0, "self_efficacy": 2.0}


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class BaselineExcludesComparisonWindowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

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
        self.db: Session = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.user = User(
            id=uuid.uuid4(),
            email=f"baseline-{uuid.uuid4().hex[:8]}@example.test",
            display_name="Baseline Patient",
            hashed_password="hashed",
            role="patient",
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _observe(self, when: datetime, values: dict[str, float]) -> None:
        for obs_type, value in values.items():
            self.db.add(
                Observation(
                    user_id=self.user.id,
                    source="self_report",
                    type=obs_type,
                    value={"value": value},
                    unit="hours" if obs_type == "sleep_hours" else "0-10",
                    occurred_at=when,
                    quality={"test": True},
                )
            )
        self.db.flush()

    def _days(self, offsets: range, values: dict[str, float]) -> None:
        for offset in offsets:
            self._observe(NOW - timedelta(days=offset), values)
        self.db.commit()

    def test_reference_window_is_the_period_before_the_comparison_window(self):
        start, end, recent_start = baseline_reference_window(NOW)
        self.assertEqual(recent_start, NOW - timedelta(days=RECENT_WINDOW_DAYS))
        self.assertEqual(end, recent_start)
        self.assertEqual(end - start, timedelta(days=BASELINE_WINDOW_DAYS))

    def test_recent_shift_is_not_absorbed_into_its_own_reference(self):
        self._days(range(20, 7, -1), STABLE)  # 13 reference days
        self._days(range(5, 0, -1), SHIFTED)  # 5 recent days

        result = run_canonical_analytics(self.db, self.user.id, now=NOW)
        stats = result.baseline_version.stats

        # The reference is only the stable period: the shift did not dilute it.
        self.assertEqual(stats["mood"]["mean"], 5.0)
        self.assertEqual(stats["mood"]["n"], 13.0)
        self.assertEqual(stats["craving_inv"]["mean"], 6.0)
        self.assertEqual(result.baseline_version.status, "active")
        mood = next(cs for cs in result.change_signals if cs.feature == "mood")
        # (2 - 5) / max(std 0, floor 1) = -3: the shift is fully visible.
        self.assertEqual(mood.change_value, -3.0)
        self.assertEqual(mood.band, "unstable")
        self.assertEqual(mood.uncertainty["baseline_n"], 13)
        self.assertEqual(mood.uncertainty["recent_n"], 5)

    def test_only_recent_observations_do_not_form_a_baseline(self):
        # A week of daily check-ins, all inside the comparison window. Before,
        # these formed their own baseline and compared as "stable".
        self._days(range(6, -1, -1), STABLE)

        result = run_canonical_analytics(self.db, self.user.id, now=NOW)

        self.assertEqual(result.baseline_version.status, "provisional")
        self.assertEqual(result.baseline_version.stability, "insufficient_data")
        self.assertEqual(result.baseline_version.data_coverage, 0.0)
        self.assertEqual(result.baseline_version.stats, {})
        self.assertEqual(result.status, "insufficient_data")
        for cs in result.change_signals:
            self.assertEqual(cs.band, "insufficient_data")
            self.assertIsNone(cs.change_value)
        # The recent values are still computed, not dropped or zeroed.
        mood_fv = next(fv for fv in result.feature_values if fv.feature_key == "mood")
        self.assertEqual(mood_fv.value["mean"], 5.0)
        self.assertEqual(mood_fv.value["n"], 7)

    def test_exclusion_is_recorded_and_readable(self):
        self._days(range(20, 7, -1), STABLE)
        self._days(range(3, 0, -1), SHIFTED)
        self._observe(NOW - timedelta(days=2), {"mood": 3.0})  # one extra mood point
        self.db.commit()

        result = run_canonical_analytics(self.db, self.user.id, now=NOW)
        row = result.baseline_version
        recent_start = NOW - timedelta(days=RECENT_WINDOW_DAYS)

        self.assertEqual(_utc(row.window_end), recent_start)
        self.assertEqual(
            row.exclusions,
            [
                {
                    "kind": "comparison_window",
                    "reason": "recent_window_is_compared_not_absorbed",
                    "window": {"start": recent_start.isoformat(), "end": NOW.isoformat()},
                    "observation_counts": {
                        "mood": 4,
                        "craving": 3,
                        "sleep_hours": 3,
                        "self_efficacy": 3,
                    },
                }
            ],
        )
        self.assertEqual(result.to_response()["baseline_version"]["exclusions"], row.exclusions)
        self.assertEqual(result.detail["baseline_exclusions"], row.exclusions)
        self.assertEqual(baseline_summary(row)["baseline"]["exclusions"], row.exclusions)
        self.assertEqual(
            longitudinal_state(self.db, self.user.id)["baseline"]["baseline"]["exclusions"],
            row.exclusions,
        )
        # The professional summary/dossier schema keeps the exclusion too.
        serialised = LongitudinalBaselineOut.model_validate(baseline_summary(row)).model_dump()
        self.assertEqual(serialised["baseline"]["exclusions"], row.exclusions)

    def test_window_edges_are_assigned_to_exactly_one_side(self):
        recent_start = NOW - timedelta(days=RECENT_WINDOW_DAYS)
        reference_start = recent_start - timedelta(days=BASELINE_WINDOW_DAYS)
        self._days(range(20, 14, -1), STABLE)  # 6 reference days
        self._observe(recent_start, {"mood": 9.0})  # boundary: recent, not reference
        self._observe(reference_start, {"mood": 1.0})  # boundary: first reference instant
        self._observe(reference_start - timedelta(seconds=1), {"mood": 0.0})  # too old
        self.db.commit()

        result = run_canonical_analytics(self.db, self.user.id, now=NOW)
        mood_stats = result.baseline_version.stats["mood"]
        mood_fv = next(fv for fv in result.feature_values if fv.feature_key == "mood")

        self.assertEqual(mood_stats["n"], 7.0)  # six stable days + reference_start
        self.assertAlmostEqual(mood_stats["mean"], (6 * 5.0 + 1.0) / 7, places=6)
        self.assertEqual(mood_fv.value["n"], 1)
        self.assertEqual(mood_fv.value["mean"], 9.0)
        self.assertEqual(result.baseline_version.exclusions[0]["observation_counts"]["mood"], 1)

    def test_new_version_supersedes_earlier_canonical_baseline_without_deleting_it(self):
        legacy = BaselineVersion(
            user_id=self.user.id,
            feature_key=None,
            window_start=NOW - timedelta(days=21),
            window_end=NOW,
            stats={},
            exclusions=[],
            stability="insufficient_data",
            data_coverage=0.0,
            status="active",
            algorithm_version="canonical-structural-v1",
        )
        self.db.add(legacy)
        self.db.commit()
        self._days(range(20, 7, -1), STABLE)

        result = run_canonical_analytics(self.db, self.user.id, now=NOW)

        self.db.refresh(legacy)
        self.assertEqual(legacy.status, "superseded")
        self.assertEqual(result.baseline_version.algorithm_version, ALGORITHM_VERSION)
        self.assertEqual(self.db.query(BaselineVersion).count(), 2)
        readable = (
            self.db.query(BaselineVersion)
            .filter(BaselineVersion.status.in_(["active", "provisional"]))
            .all()
        )
        self.assertEqual([row.id for row in readable], [result.baseline_version.id])

    def test_same_inputs_and_timestamp_give_the_same_reference(self):
        self._days(range(20, 7, -1), STABLE)
        self._days(range(4, 0, -1), SHIFTED)

        first = run_canonical_analytics(self.db, self.user.id, now=NOW)
        second = run_canonical_analytics(self.db, self.user.id, now=NOW)

        self.assertEqual(first.baseline_version.stats, second.baseline_version.stats)
        self.assertEqual(first.baseline_version.exclusions, second.baseline_version.exclusions)
        self.assertEqual(
            {cs.feature: (cs.band, cs.change_value) for cs in first.change_signals},
            {cs.feature: (cs.band, cs.change_value) for cs in second.change_signals},
        )


if __name__ == "__main__":
    unittest.main()
