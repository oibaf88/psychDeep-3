"""Change explanations read back the canonical FeatureValue and BaselineVersion rows.

Engineering reproducibility tests, not clinical validation of thresholds.
The read must not recompute analytics, touch RiskAssessment or call a model.
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
from app.models_vnext import (
    BaselineVersion,
    ChangeSignal,
    FeatureDefinition,
    FeatureValue,
    Observation,
)
from app.services.canonical_analytics import run_canonical_analytics
from app.services.longitudinal_read import (
    change_signal_summary,
    for_clinical_reader,
    longitudinal_state,
    longitudinal_states,
)
from tests.test_vnext_canonical_analytics import NOW, _add_observation, _seed_days

FEATURES = ("mood", "craving", "sleep_hours", "self_efficacy")


class FeatureEvidenceReadTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
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
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.user = self._user()
        self.other = self._user()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _user(self) -> User:
        user = User(
            id=uuid.uuid4(),
            email=f"patient-{uuid.uuid4().hex[:8]}@example.test",
            display_name="Test Patient",
            hashed_password="hashed",
            role="patient",
        )
        self.db.add(user)
        self.db.commit()
        return user

    def _seed_drift(self, user_id):
        _seed_days(
            self.db,
            user_id,
            days=14,
            start_offset_days=20,
            values={"mood": 5.0, "craving": 4.0, "sleep_hours": 7.0, "self_efficacy": 6.0},
        )
        _seed_days(
            self.db,
            user_id,
            days=5,
            start_offset_days=5,
            values={"mood": 3.0, "craving": 7.0, "sleep_hours": 5.0, "self_efficacy": 3.0},
        )

    def _by_feature(self, state):
        return {row["feature"]: row for row in state["changes"]}

    def test_each_change_cites_its_feature_value_and_baseline_axis(self):
        self._seed_drift(self.user.id)
        result = run_canonical_analytics(self.db, self.user.id, now=NOW)
        values = {fv.feature_key: fv for fv in result.feature_values}
        stats = result.baseline_version.stats

        changes = self._by_feature(longitudinal_state(self.db, self.user.id))

        for feature in FEATURES:
            evidence = changes[feature]["evidence"]
            self.assertEqual(evidence["status"], "available", feature)
            self.assertEqual(evidence["recent"]["feature_value_id"], str(values[feature].id))
            self.assertEqual(evidence["recent"]["mean"], values[feature].value["mean"])
            self.assertEqual(evidence["recent"]["n"], values[feature].value["n"])
            self.assertGreater(evidence["recent"]["n"], 0)
            self.assertEqual(evidence["recent"]["algorithm_version"], result.algorithm_version)
            self.assertEqual(evidence["reference"]["baseline_version_id"], str(result.baseline_version.id))
            self.assertEqual(evidence["reference"]["mean"], stats[evidence["axis"]]["mean"])
            self.assertTrue(evidence["reference"]["eligible"])
            self.assertIs(evidence["reproduced_from_rows"], True, feature)

        self.assertTrue(changes["craving"]["evidence"]["inverted"])
        self.assertEqual(changes["craving"]["evidence"]["axis"], "craving_inv")
        self.assertFalse(changes["mood"]["evidence"]["inverted"])
        # The composite cites several FeatureValues and has no single one.
        self.assertIsNone(changes["structural_composite"]["evidence"])
        self.assertNotIn("alert_level", str(changes))

    def test_same_versioned_inputs_give_the_same_explanation(self):
        self._seed_drift(self.user.id)
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        first = self._by_feature(longitudinal_state(self.db, self.user.id))
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        second = self._by_feature(longitudinal_state(self.db, self.user.id))

        def stable_part(rows):
            out = {}
            for feature, row in rows.items():
                evidence = row["evidence"]
                out[feature] = (
                    row["band"],
                    row["change"],
                    row["algorithm_version"],
                    None
                    if evidence is None
                    else (
                        evidence["recent"]["mean"],
                        evidence["recent"]["n"],
                        tuple(evidence["recent"]["quality_flags"]),
                        evidence["reference"]["mean"],
                        evidence["reference"]["std"],
                        evidence["reproduced_from_rows"],
                    ),
                )
            return out

        self.assertEqual(stable_part(first), stable_part(second))
        # The second run superseded the first rows; the read cites the new ones.
        self.assertNotEqual(
            first["mood"]["evidence"]["recent"]["feature_value_id"],
            second["mood"]["evidence"]["recent"]["feature_value_id"],
        )

    def test_missing_data_stays_missing_and_is_not_a_zero(self):
        _add_observation(self.db, self.user.id, "mood", 4.0, NOW - timedelta(days=2))
        _add_observation(self.db, self.user.id, "mood", 5.0, NOW - timedelta(days=1))
        self.db.commit()
        run_canonical_analytics(self.db, self.user.id, now=NOW)

        changes = self._by_feature(longitudinal_state(self.db, self.user.id))

        mood = changes["mood"]["evidence"]
        self.assertEqual(mood["status"], "insufficient_data")
        self.assertEqual(mood["recent"]["mean"], 4.5)
        self.assertIsNone(mood["reference"])
        self.assertIsNone(mood["reproduced_from_rows"])
        for feature in ("craving", "sleep_hours", "self_efficacy"):
            evidence = changes[feature]["evidence"]
            self.assertEqual(evidence["status"], "insufficient_data")
            self.assertTrue(evidence["recent"]["missing"])
            self.assertIsNone(evidence["recent"]["mean"])
            self.assertEqual(evidence["recent"]["quality_flags"], ["no_recent_observations"])
            self.assertIsNone(evidence["reference"])
            self.assertIsNone(evidence["reproduced_from_rows"])

    def test_a_feature_value_from_another_person_is_never_shown(self):
        self._seed_drift(self.user.id)
        self._seed_drift(self.other.id)
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        other = run_canonical_analytics(self.db, self.other.id, now=NOW)
        foreign = next(fv for fv in other.feature_values if fv.feature_key == "mood")

        signal = (
            self.db.query(ChangeSignal)
            .filter(ChangeSignal.user_id == self.user.id, ChangeSignal.feature == "mood")
            .one()
        )
        signal.evidence_refs = [
            {"kind": "feature_value", "id": str(foreign.id)},
            *[ref for ref in signal.evidence_refs if ref.get("kind") != "feature_value"],
        ]
        self.db.commit()

        evidence = self._by_feature(longitudinal_state(self.db, self.user.id))["mood"]["evidence"]
        self.assertIsNone(evidence["recent"])
        self.assertEqual(evidence["status"], "insufficient_data")
        self.assertNotIn(str(foreign.id), str(evidence))

    def test_a_stored_change_that_no_longer_matches_its_rows_is_flagged(self):
        self._seed_drift(self.user.id)
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        signal = (
            self.db.query(ChangeSignal)
            .filter(ChangeSignal.user_id == self.user.id, ChangeSignal.feature == "sleep_hours")
            .one()
        )
        signal.change_value = float(signal.change_value) + 0.5
        self.db.commit()

        evidence = self._by_feature(longitudinal_state(self.db, self.user.id))["sleep_hours"]["evidence"]
        self.assertIs(evidence["reproduced_from_rows"], False)

    def test_batch_and_clinical_reads_carry_the_same_evidence(self):
        self._seed_drift(self.user.id)
        self._seed_drift(self.other.id)
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        run_canonical_analytics(self.db, self.other.id, now=NOW)

        batch = longitudinal_states(self.db, [self.user.id, self.other.id])
        self.assertEqual(batch[self.user.id], longitudinal_state(self.db, self.user.id))
        self.assertEqual(batch[self.other.id], longitudinal_state(self.db, self.other.id))
        clinical = for_clinical_reader(batch[self.user.id])
        self.assertEqual(clinical["changes"], batch[self.user.id]["changes"])

    def test_plain_change_summary_keeps_its_previous_shape(self):
        self._seed_drift(self.user.id)
        run_canonical_analytics(self.db, self.user.id, now=NOW)
        row = self.db.query(ChangeSignal).filter(ChangeSignal.feature == "mood").first()
        self.assertNotIn("evidence", change_signal_summary(row))


if __name__ == "__main__":
    unittest.main()
