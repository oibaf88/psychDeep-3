"""Supervised freeze / release of the canonical personal baseline (G2).

vNext spec 8.2 asks that the personal baseline can be frozen or recalibrated
with supervision, so a period a clinician does not want treated as the new
normal is compared against the reference instead of absorbed into it. These
are engineering reproducibility and authorisation tests, not clinical
validation of when a freeze is appropriate.
"""
from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.models_vnext  # noqa: F401
from app.database import Base, get_db
from app.models import AuditLog, Consent, PatientProfessionalAssignment, RiskAssessment, User
from app.models_vnext import BaselineVersion, ChangeSignal, Observation
from app.routers import professional
from app.security import create_access_token
from app.services import baseline_freeze
from app.services.baseline_freeze import BaselineFreezeError, freeze_baseline, freeze_record, release_baseline
from app.services.canonical_analytics import (
    ALGORITHM_VERSION,
    refresh_stale_trajectories,
    run_canonical_analytics,
)
from app.services.longitudinal_read import longitudinal_state

NOW = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
STABLE = {"mood": 5.0, "craving": 4.0, "sleep_hours": 7.0, "self_efficacy": 6.0}
SHIFTED = {"mood": 2.0, "craving": 8.0, "sleep_hours": 4.0, "self_efficacy": 2.0}


class _Case(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.patient = self.user("patient")
        self.therapist = self.user("therapist")
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def user(self, role):
        row = User(
            email=f"{uuid.uuid4().hex[:10]}@example.test",
            display_name=role,
            hashed_password="not-used",
            role=role,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def observe_days(self, anchor: datetime, offsets, values) -> None:
        for offset in offsets:
            when = anchor - timedelta(days=offset)
            for obs_type, value in values.items():
                self.db.add(
                    Observation(
                        user_id=self.patient.id,
                        source="self_report",
                        type=obs_type,
                        value={"value": value},
                        unit="hours" if obs_type == "sleep_hours" else "0-10",
                        occurred_at=when,
                        quality={"test": True},
                    )
                )
        self.db.commit()

    def baselines(self):
        return (
            self.db.query(BaselineVersion)
            .filter(BaselineVersion.user_id == self.patient.id)
            .order_by(BaselineVersion.created_at.asc())
            .all()
        )

    def freeze(self, now=NOW, reason="Recaída reciente: no absorber este periodo"):
        return freeze_baseline(
            self.db,
            self.patient.id,
            actor_id=self.therapist.id,
            actor_role="therapist",
            reason=reason,
            now=now,
        )


class FreezeHoldsTheReferenceTests(_Case):
    def setUp(self):
        super().setUp()
        # 20 stable reference days, then a stable recent week: a full reference.
        self.observe_days(NOW, range(27, 7, -1), STABLE)
        self.observe_days(NOW, range(6, -1, -1), STABLE)
        self.initial = run_canonical_analytics(self.db, self.patient.id, now=NOW).baseline_version
        self.assertEqual(self.initial.status, "active")

    def test_freeze_appends_a_frozen_copy_and_keeps_the_source_row(self):
        frozen = self.freeze()
        self.db.refresh(self.initial)

        self.assertEqual(frozen.status, "frozen")
        self.assertNotEqual(frozen.id, self.initial.id)
        self.assertEqual(frozen.stats, self.initial.stats)
        self.assertEqual(frozen.window_start, self.initial.window_start)
        self.assertEqual(frozen.window_end, self.initial.window_end)
        self.assertEqual(frozen.algorithm_version, ALGORITHM_VERSION)
        # Append-only: the source reference is superseded, not deleted or edited.
        self.assertEqual(self.initial.status, "superseded")
        self.assertEqual(len(self.initial.exclusions), 1)
        record = freeze_record(frozen)
        self.assertEqual(record["kind"], "supervised_freeze")
        self.assertEqual(record["frozen_by"], str(self.therapist.id))
        self.assertEqual(record["frozen_by_role"], "therapist")
        self.assertEqual(record["source_baseline_version_id"], str(self.initial.id))
        self.assertEqual(record["note"], "Recaída reciente: no absorber este periodo")
        self.assertEqual(frozen.exclusions[0]["kind"], "comparison_window")

    def test_freeze_is_audited_without_the_clinical_note(self):
        frozen = self.freeze()
        rows = self.db.query(AuditLog).filter(AuditLog.action == "baseline_frozen").all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].entity_id, str(frozen.id))
        self.assertEqual(rows[0].actor_id, self.therapist.id)
        self.assertEqual(rows[0].extra["source_baseline_version_id"], str(self.initial.id))
        self.assertNotIn("Recaída", repr(rows[0].extra))

    def test_freeze_rereads_the_trajectory_against_the_frozen_row(self):
        frozen = self.freeze()
        state = longitudinal_state(self.db, self.patient.id)
        self.assertEqual(state["baseline"]["status"], "frozen")
        self.assertEqual(state["baseline"]["baseline"]["id"], str(frozen.id))
        self.assertTrue(state["changes"])
        cited = {
            str(row.id)
            for row in self.db.query(ChangeSignal).filter(ChangeSignal.baseline_version_id == frozen.id)
        }
        self.assertTrue({change["signal_id"] for change in state["changes"]} <= cited)

    def test_later_data_is_compared_against_the_held_reference_not_absorbed(self):
        frozen = self.freeze()
        later = NOW + timedelta(days=21)
        # Three weeks of a shifted period that would otherwise become the reference.
        self.observe_days(later, range(20, -1, -1), SHIFTED)

        result = run_canonical_analytics(self.db, self.patient.id, now=later)

        self.assertEqual(result.baseline_version.id, frozen.id)
        self.assertTrue(result.detail["baseline_frozen"])
        # No new reference was built while frozen.
        self.assertEqual([row.status for row in self.baselines()], ["superseded", "frozen"])
        mood = next(cs for cs in result.change_signals if cs.feature == "mood")
        # (2 - 5) / max(std 0, floor 1) = -3 against the held reference.
        self.assertEqual(mood.change_value, -3.0)
        self.assertEqual(mood.band, "unstable")
        self.assertTrue(mood.uncertainty["baseline_frozen"])
        self.assertEqual(mood.baseline_version_id, frozen.id)

        # The explanation is reproducible from the cited rows.
        state = longitudinal_state(self.db, self.patient.id)
        mood_read = next(row for row in state["changes"] if row["feature"] == "mood")
        self.assertEqual(mood_read["evidence"]["reference"]["baseline_version_id"], str(frozen.id))
        self.assertTrue(mood_read["evidence"]["reproduced_from_rows"])

    def test_without_a_freeze_the_same_period_becomes_the_reference(self):
        later = NOW + timedelta(days=21)
        self.observe_days(later, range(20, -1, -1), SHIFTED)
        result = run_canonical_analytics(self.db, self.patient.id, now=later)
        mood = next(cs for cs in result.change_signals if cs.feature == "mood")
        self.assertNotEqual(result.baseline_version.id, self.initial.id)
        self.assertFalse(result.detail["baseline_frozen"])
        self.assertNotIn("baseline_frozen", mood.uncertainty)
        # The shifted weeks dominate the new reference, so the change shrinks.
        self.assertLess(abs(mood.change_value), 3.0)

    def test_freezing_twice_is_refused(self):
        self.freeze()
        with self.assertRaises(BaselineFreezeError) as ctx:
            self.freeze()
        self.assertEqual(str(ctx.exception), "already_frozen")

    def test_release_retires_the_frozen_row_and_recalibrates(self):
        frozen = self.freeze()
        later = NOW + timedelta(days=21)
        self.observe_days(later, range(20, -1, -1), SHIFTED)

        current = release_baseline(
            self.db, self.patient.id, actor_id=self.therapist.id, actor_role="therapist", now=later
        )
        self.db.refresh(frozen)

        self.assertEqual(frozen.status, "retired")
        self.assertIsNotNone(current)
        self.assertNotEqual(current.id, frozen.id)
        self.assertIn(current.status, ("active", "provisional"))
        self.assertIsNone(freeze_record(current))
        # History keeps all three rows.
        self.assertEqual([row.status for row in self.baselines()][:2], ["superseded", "retired"])
        released = self.db.query(AuditLog).filter(AuditLog.action == "baseline_released").all()
        self.assertEqual([row.entity_id for row in released], [str(frozen.id)])
        with self.assertRaises(BaselineFreezeError) as ctx:
            release_baseline(self.db, self.patient.id, actor_id=self.therapist.id, actor_role="therapist")
        self.assertEqual(str(ctx.exception), "not_frozen")

    def test_freeze_never_runs_the_risk_engine(self):
        with patch("app.services.risk_engine.run_and_persist") as engine:
            self.freeze()
            release_baseline(
                self.db, self.patient.id, actor_id=self.therapist.id, actor_role="therapist", now=NOW
            )
        engine.assert_not_called()
        self.assertEqual(self.db.query(RiskAssessment).count(), 0)


class FreezePreconditionTests(_Case):
    def test_no_baseline_cannot_be_frozen(self):
        with self.assertRaises(BaselineFreezeError) as ctx:
            self.freeze()
        self.assertEqual(str(ctx.exception), "no_canonical_baseline")

    def test_an_insufficient_reference_cannot_be_frozen(self):
        self.observe_days(NOW, range(6, -1, -1), STABLE)  # recent week only
        run_canonical_analytics(self.db, self.patient.id, now=NOW)
        with self.assertRaises(BaselineFreezeError) as ctx:
            self.freeze()
        self.assertEqual(str(ctx.exception), "insufficient_data")
        self.assertNotIn("frozen", [row.status for row in self.baselines()])


class StaleCatchUpWithFrozenReferenceTests(_Case):
    def test_catch_up_uses_the_last_comparison_not_the_frozen_row_age(self):
        now = datetime.now(timezone.utc)
        self.observe_days(now - timedelta(hours=1), range(27, 7, -1), STABLE)
        run_canonical_analytics(self.db, self.patient.id, now=now)
        self.freeze(now=now)

        # Nothing new since the freeze re-read: no recompute at startup.
        before = self.db.query(ChangeSignal).count()
        self.assertEqual(refresh_stale_trajectories(self.db)["refreshed"], 0)
        self.assertEqual(self.db.query(ChangeSignal).count(), before)

        # A newer observation makes the comparison stale; it is recomputed
        # against the same frozen reference.
        self.observe_days(datetime.now(timezone.utc) + timedelta(minutes=5), [0], SHIFTED)
        self.assertEqual(refresh_stale_trajectories(self.db)["refreshed"], 1)
        self.assertEqual([row.status for row in self.baselines()], ["superseded", "frozen"])


class FreezeEndpointTests(_Case):
    def setUp(self):
        super().setUp()
        self.other_therapist = self.user("therapist")
        self.supervisor = self.user("supervisor")
        self.admin = self.user("admin_clinical")
        self.db.add(
            PatientProfessionalAssignment(
                patient_id=self.patient.id, professional_id=self.therapist.id, status="active"
            )
        )
        self.consent = Consent(user_id=self.patient.id, consent_type="professional_sharing", granted=True)
        self.db.add(self.consent)
        now = datetime.now(timezone.utc)
        self.observe_days(now - timedelta(hours=1), range(27, 7, -1), STABLE)
        run_canonical_analytics(self.db, self.patient.id, now=now)

        api = FastAPI()
        api.include_router(professional.router)

        def local_db():
            session = self.sessions()
            try:
                yield session
            finally:
                session.close()

        api.dependency_overrides[get_db] = local_db
        self.client = TestClient(api)

    def tearDown(self):
        self.client.close()
        super().tearDown()

    def headers(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}

    def url(self, action):
        return f"/api/v1/professional/patients/{self.patient.id}/baseline/{action}"

    def test_assigned_therapist_can_freeze_and_release(self):
        response = self.client.post(
            self.url("freeze"), json={"reason": "Periodo de crisis"}, headers=self.headers(self.therapist)
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "frozen")
        kinds = [entry["kind"] for entry in body["baseline"]["exclusions"]]
        self.assertEqual(kinds, ["comparison_window", "supervised_freeze"])

        again = self.client.post(
            self.url("freeze"), json={"reason": "Otra vez"}, headers=self.headers(self.therapist)
        )
        self.assertEqual(again.status_code, 409)

        released = self.client.post(self.url("release"), headers=self.headers(self.therapist))
        self.assertEqual(released.status_code, 200, released.text)
        self.assertIn(released.json()["status"], ("active", "provisional"))
        self.assertEqual(self.client.post(self.url("release"), headers=self.headers(self.therapist)).status_code, 409)

    def test_a_reason_is_required(self):
        response = self.client.post(self.url("freeze"), json={"reason": ""}, headers=self.headers(self.therapist))
        self.assertEqual(response.status_code, 422)

    def test_unassigned_supervisor_admin_and_patient_are_refused(self):
        for user in (self.other_therapist, self.supervisor, self.admin, self.patient):
            with self.subTest(role=user.role):
                response = self.client.post(
                    self.url("freeze"), json={"reason": "Periodo de crisis"}, headers=self.headers(user)
                )
                self.assertIn(response.status_code, (401, 403))
        self.assertNotIn("frozen", [row.status for row in self.baselines()])

    def test_revoked_sharing_consent_refuses_the_freeze(self):
        self.consent.revoked_at = datetime.utcnow()
        self.db.commit()
        response = self.client.post(
            self.url("freeze"), json={"reason": "Periodo de crisis"}, headers=self.headers(self.therapist)
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
