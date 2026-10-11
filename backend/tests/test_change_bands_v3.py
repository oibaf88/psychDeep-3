"""structural-v3 / canonical-structural-v3 (ADR 0003): evidence-based bands,
reference strictly before the recent window, craving trend direction.

Engineering regression tests. They do not validate a clinical instrument."""
import os
import random
import unittest
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AlfaSignal, CheckIn, Consent, User
from app.models_vnext import BaselineVersion
from app.services import baseline, change_config, profile, risk_engine
from app.services.canonical_analytics import ALGORITHM_VERSION, run_canonical_analytics
from app.services.canonical_data import record_checkin


class _DbCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

        import app.models  # noqa: F401
        import app.models_vnext  # noqa: F401

        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.user = User(email=f"{uuid.uuid4()}@x.example", hashed_password="x", display_name="p", role="patient")
        self.db.add(self.user)
        self.db.commit()
        for kind in ("data_processing", "core_processing", "professional_sharing"):
            self.db.add(Consent(user_id=self.user.id, consent_type=kind, granted=True))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add(self, days_ago, mood, craving, sleep, efficacy, hours=3.0):
        row = CheckIn(
            user_id=self.user.id, mood=mood, craving=craving, sleep_hours=sleep, self_efficacy=efficacy,
            created_at=datetime.utcnow() - timedelta(days=days_ago, hours=hours),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        record_checkin(self.db, row)
        self.db.commit()

    def history(self, reference, recent, days=35):
        for d in range(days, 0, -1):
            values = reference(d) if d >= 7 else recent(d)
            if values is not None:
                self.add(d, *values)


class NonOverlapTests(_DbCase):
    def test_reference_ends_where_recent_window_starts(self):
        now = datetime(2026, 10, 10, 12, 0, 0)
        ref_start, ref_end, recent_start = baseline.windows_for(now)
        self.assertEqual(ref_end, recent_start)
        self.assertEqual(recent_start, now - timedelta(days=change_config.RECENT_WINDOW_DAYS))
        self.assertEqual(ref_end - ref_start, timedelta(days=change_config.REFERENCE_WINDOW_DAYS))

    def test_persisted_reference_excludes_every_recent_checkin(self):
        # Reference: constant 6. Recent week: 1. If any recent row leaked into
        # the reference, its mean would drop below 6 and its SD would rise.
        self.history(lambda d: (6, 3, 7.0, 6), lambda d: (1, 9, 4.0, 1))
        result = baseline.compute_structural_score(self.db, self.user.id)
        active = baseline.get_active_baseline(self.db, self.user.id)
        _, _, recent_start = baseline.windows_for(datetime.utcnow())
        self.assertLessEqual(active.window_end, recent_start)
        self.assertEqual(active.stats["mood"]["mean"], 6.0)
        self.assertEqual(active.stats["mood"]["std"], 0.0)
        self.assertEqual(result.calculation_version, "structural-v3")
        self.assertEqual(result.confidence_band, "unstable")

    def test_an_overlapping_v2_style_baseline_is_never_used(self):
        self.history(lambda d: (6, 3, 7.0, 6), lambda d: (6, 3, 7.0, 6))
        from app.models import Baseline

        self.db.add(Baseline(
            user_id=self.user.id, window_start=datetime.utcnow() - timedelta(days=21), window_end=datetime.utcnow(),
            stats={k: {"mean": 0.0, "std": 0.0, "n": 21} for k in baseline.VARIABLES}, is_active=True,
        ))
        self.db.commit()
        result = baseline.compute_structural_score(self.db, self.user.id)
        self.assertEqual(result.confidence_band, "stable")
        active = baseline.get_active_baseline(self.db, self.user.id)
        self.assertLessEqual(active.window_end, datetime.utcnow() - timedelta(days=7) + timedelta(seconds=1))

    def test_canonical_reference_precedes_recent_window(self):
        self.history(lambda d: (6, 3, 7.0, 6), lambda d: (1, 9, 4.0, 1))
        run = run_canonical_analytics(self.db, self.user.id)
        bv = run.baseline_version
        self.assertEqual(bv.algorithm_version, ALGORITHM_VERSION)
        self.assertEqual(ALGORITHM_VERSION, "canonical-structural-v3")
        for cs in run.change_signals:
            self.assertGreaterEqual(cs.window_start.replace(tzinfo=None), bv.window_end.replace(tzinfo=None))
        self.assertEqual(bv.stats["mood"]["mean"], 6.0)

    def test_linguistic_reference_excludes_the_recent_window(self):
        for days_ago, value in ((30, 0.2), (20, 0.2), (2, 0.95)):
            self.db.add(AlfaSignal(
                user_id=self.user.id, signal_type="linguistic_analysis", value={"rumination_score": value},
                timestamp=datetime.utcnow() - timedelta(days=days_ago), is_active=True,
            ))
        self.db.commit()
        stats, n = profile.compute_linguistic_stats(self.db, self.user.id)
        self.assertEqual(stats["rumination_score"]["n"], 2)
        self.assertEqual(stats["rumination_score"]["mean"], 0.2)


class BandBoundaryTests(unittest.TestCase):
    def test_statistical_boundaries(self):
        self.assertEqual(change_config.z_band(0.999), "stable")
        self.assertEqual(change_config.z_band(1.0), "transition")
        self.assertEqual(change_config.z_band(1.299), "transition")
        self.assertEqual(change_config.z_band(1.3), "unstable")

    def test_raw_guards_demote_trivial_changes(self):
        # z large but raw change tiny (cannot happen with the floor, but the
        # guard must hold on its own).
        self.assertEqual(change_config.axis_band("mood", -5.0, -0.99), "stable")
        self.assertEqual(change_config.axis_band("mood", -5.0, -1.0), "transition")
        self.assertEqual(change_config.axis_band("mood", -5.0, -1.99), "transition")
        self.assertEqual(change_config.axis_band("mood", -5.0, -2.0), "unstable")
        self.assertEqual(change_config.axis_band("sleep_hours", 3.0, 0.49), "stable")
        self.assertEqual(change_config.axis_band("sleep_hours", 3.0, 0.5), "unstable")
        self.assertEqual(change_config.axis_band("mood", 0.99, 3.0), "stable")

    def test_composite_needs_one_meaningful_raw_change(self):
        tiny = {"mood": 0.9, "craving_inv": 0.9, "sleep_hours": 0.4, "self_efficacy": 0.9}
        self.assertEqual(change_config.composite_band(1.5, tiny), "stable")
        self.assertEqual(change_config.composite_band(1.5, {**tiny, "mood": 1.0}), "unstable")
        self.assertEqual(change_config.composite_band(1.1, {**tiny, "sleep_hours": 0.5}), "transition")

    def test_reliable_change_index_matches_the_derivation(self):
        # sqrt(1/7 + 1/28) * sqrt(1.17/0.83) = 0.5017 -> RCI 1.96 at d = 0.983 SD.
        self.assertAlmostEqual(change_config.reliable_change_index(0.9834, 1.0, 7, 28), 1.96, places=2)
        self.assertIsNone(change_config.reliable_change_index(1.0, 1.0, 0, 28))

    def test_config_is_versioned_and_labelled_provisional(self):
        snapshot = change_config.describe()
        self.assertEqual(snapshot["calibration_status"], "provisional_population_prior")
        self.assertTrue(snapshot["reference_precedes_recent"])
        self.assertEqual(snapshot["personal_calibration_min_days"], 100)


class CravingDirectionTests(unittest.TestCase):
    def test_rising_craving_reads_as_rising(self):
        self.assertEqual(baseline.calculate_trend_detail([2, 3, 4, 5, 6], "craving").label, "aumentando")

    def test_falling_craving_is_not_called_worsening(self):
        self.assertEqual(baseline.calculate_trend_detail([6, 5, 4, 3, 2], "craving").label, "disminuyendo")

    def test_sleep_keeps_its_worsening_label_for_the_existing_rule(self):
        self.assertEqual(baseline.calculate_trend_detail([8, 7, 6, 5, 4], "sleep_hours").label, "empeorando")

    def test_missing_values_are_skipped_not_zero(self):
        detail = baseline.calculate_trend_detail([None, 2, None, 3, 4, float("nan")], "craving")
        self.assertEqual(detail.sample_count, 3)
        self.assertEqual(detail.label, "aumentando")
        self.assertEqual(baseline.calculate_trend_detail([None, None, 5], "craving").label, "insuficiente")


class MissingDataTests(_DbCase):
    def test_too_few_reference_days_is_insufficient_not_zero(self):
        self.history(lambda d: (6, 3, 7.0, 6) if d <= 10 else None, lambda d: (2, 8, 4.0, 2))
        result = baseline.compute_structural_score(self.db, self.user.id)
        self.assertEqual(result.confidence_band, "insufficient_data")
        self.assertIsNone(result.score)

    def test_several_checkins_on_one_day_count_as_one_reference_day(self):
        for d in range(12, 8, -1):
            for h in (2, 5, 8):
                self.add(d, 6, 3, 7.0, 6, hours=h)
        self.assertIsNone(baseline.compute_or_refresh_baseline(self.db, self.user.id))


class SensitivityRegressionTests(_DbCase):
    """Key rows of the old-vs-new sensitivity table (docs/adr/0003)."""

    def _structural(self):
        return baseline.compute_structural_score(self.db, self.user.id)

    def test_last_week_deterioration_is_unstable(self):
        random.seed(1)
        self.history(lambda d: (random.randint(6, 7), random.randint(2, 3), 7.0, random.randint(6, 7)),
                     lambda d: (random.randint(3, 4), random.randint(6, 7), 5.0, random.randint(3, 4)))
        self.assertEqual(self._structural().deterioration_band, "unstable")

    def test_sleep_drop_alone_now_leaves_stable(self):
        self.history(lambda d: (6, 3, 7.25, 6), lambda d: (6, 3, 4.75, 6))
        structural = self._structural()
        self.assertIn(structural.deterioration_band, ("transition", "unstable"))
        self.assertGreaterEqual(risk_engine.calculate_risk_level(self.db, self.user.id).level, 2)

    def test_moderate_one_and_a_half_point_deterioration_is_unstable(self):
        self.history(lambda d: (6.5, 2.5, 7.0, 6.5), lambda d: (5, 4, 6.25, 5))
        self.assertEqual(self._structural().deterioration_band, "unstable")

    def test_noise_stays_stable(self):
        random.seed(3)
        rows = lambda d: (random.randint(5, 7), random.randint(2, 4), round(random.uniform(6, 7.5), 1), random.randint(5, 7))
        self.history(rows, rows, days=42)
        self.assertEqual(self._structural().confidence_band, "stable")

    def test_one_point_shift_on_constant_series_keeps_composite_stable(self):
        self.history(lambda d: (6, 3, 7.0, 6), lambda d: (5, 4, 7.0, 5))
        self.assertEqual(self._structural().confidence_band, "stable")

    def test_improvement_is_not_deterioration(self):
        self.history(lambda d: (3, 7, 5.5, 3), lambda d: (8, 1, 5.5, 8))
        structural = self._structural()
        self.assertEqual(structural.confidence_band, "unstable")
        self.assertEqual(structural.deterioration_band, "stable")


if __name__ == "__main__":
    unittest.main()
