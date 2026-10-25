"""Authorised professional reads keep ChangeSignal apart from RiskAssessment."""
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
from app.models import PatientProfessionalAssignment, RiskAssessment, User
from app.models_vnext import BaselineVersion, ChangeSignal
from app.routers import professional
from app.security import create_access_token
from app.services.canonical_analytics import run_canonical_analytics
from app.services.longitudinal_read import CHANGE_IS_NOT_RISK, for_clinical_reader, longitudinal_state
from app.services.risk_engine import run_and_persist

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


class ProfessionalLongitudinalTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.sessions()
        self.patient = self.user("patient", "Paciente Uno")
        self.other = self.user("patient", "Paciente Dos")
        self.empty = self.user("patient", "Paciente Sin Trayectoria")
        self.therapist = self.user("therapist", "Terapeuta")
        self.other_therapist = self.user("therapist", "Terapeuta Ajeno")
        self.supervisor = self.user("supervisor", "Supervisor")
        self.admin = self.user("admin_clinical", "Admin")
        self.db.add_all([
            PatientProfessionalAssignment(
                patient_id=self.patient.id, professional_id=self.therapist.id, status="active"
            ),
            PatientProfessionalAssignment(
                patient_id=self.empty.id, professional_id=self.therapist.id, status="active"
            ),
        ])
        self.assessment = RiskAssessment(
            user_id=self.patient.id,
            alert_level=3,
            triggering_rules=["N3_demo"],
            input_signals={"structural_score": 0.37, "confidence_band": "stable"},
            input_facts={},
            assessment_reason="Evaluación de riesgo distinta del cambio longitudinal.",
            model_version="risk-engine-v1",
            calculation_trace={},
            calculated_at=NOW,
        )
        self.db.add(self.assessment)
        self.current, self.mood, self.sleep, self.composite = self.trajectory(self.patient)
        self.other_signal = self.trajectory(self.other)[1]
        self.db.commit()

        app = FastAPI()
        app.include_router(professional.router)

        def local_db():
            session = self.sessions()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = local_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def user(self, role, name):
        row = User(
            email=f"{uuid.uuid4()}@example.com",
            display_name=name,
            hashed_password="not-used",
            role=role,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def trajectory(self, patient):
        superseded = BaselineVersion(
            user_id=patient.id,
            feature_key=None,
            window_start=NOW - timedelta(days=40),
            window_end=NOW - timedelta(days=21),
            stats={"mood": {"n": 5, "mean": 1}},
            exclusions=[],
            stability="eligible",
            data_coverage=1,
            status="superseded",
            algorithm_version="canonical-structural-v1",
            created_at=NOW - timedelta(days=1),
        )
        current = BaselineVersion(
            user_id=patient.id,
            feature_key=None,
            window_start=NOW - timedelta(days=21),
            window_end=NOW,
            stats={"mood": {"n": 8, "mean": 6}},
            exclusions=[],
            stability="partial",
            data_coverage=0.5,
            status="provisional",
            algorithm_version="canonical-structural-v1",
            created_at=NOW,
        )
        self.db.add_all([superseded, current])
        self.db.flush()
        older = self.signal(patient, superseded, "mood", "stable", 0.2, NOW - timedelta(hours=3))
        self.signal(patient, current, "mood", "stable", 0.2, NOW - timedelta(hours=2))
        mood = self.signal(
            patient,
            current,
            "mood",
            "unstable",
            2.5,
            NOW,
            uncertainty={"baseline_n": 8, "recent_n": 4},
        )
        sleep = self.signal(
            patient,
            current,
            "sleep_hours",
            "insufficient_data",
            None,
            NOW,
            uncertainty={"reason": "insufficient_baseline_or_recent", "baseline_n": 0, "recent_n": 0},
        )
        composite = self.signal(
            patient,
            current,
            "structural_composite",
            "transition",
            1.1,
            NOW,
            uncertainty={"axes_present": ["mood"], "axes_required": ["mood", "sleep_hours"]},
        )
        self.db.flush()
        self.assertIsNotNone(older.id)
        return current, mood, sleep, composite

    def signal(self, patient, baseline, feature, band, change, created_at, uncertainty=None):
        row = ChangeSignal(
            user_id=patient.id,
            feature=feature,
            window_start=NOW - timedelta(days=7),
            window_end=NOW,
            change_value=change,
            band=band,
            uncertainty=uncertainty or {},
            evidence_refs=[],
            contradictions=[],
            baseline_version_id=baseline.id,
            algorithm_version="canonical-structural-v1",
            created_at=created_at,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def headers(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}

    def test_batch_read_matches_single_user_and_drops_stale_rows(self):
        single = longitudinal_state(self.db, self.patient.id)
        self.assertEqual(single["baseline"]["status"], "provisional")
        self.assertEqual(single["baseline"]["baseline"]["data_coverage"], 0.5)
        by_feature = {row["feature"]: row for row in single["changes"]}
        self.assertEqual(set(by_feature), {"mood", "sleep_hours", "structural_composite"})
        self.assertEqual(by_feature["mood"]["band"], "unstable")
        self.assertEqual(by_feature["mood"]["change"], 2.5)
        self.assertEqual(by_feature["mood"]["signal_id"], str(self.mood.id))
        self.assertIsNone(by_feature["sleep_hours"]["change"])
        self.assertNotEqual(by_feature["sleep_hours"]["change"], 0)
        self.assertNotIn(str(self.other_signal.id), {row["signal_id"] for row in single["changes"]})
        wrapped = for_clinical_reader(single)
        self.assertEqual(wrapped["changes"], single["changes"])
        self.assertEqual(wrapped["limits"], [CHANGE_IS_NOT_RISK])
        self.assertNotIn("limits", single)

    def test_assigned_professional_sees_change_apart_from_alert_level(self):
        with patch("app.services.risk_engine.run_and_persist", wraps=run_and_persist) as risk, patch(
            "app.services.canonical_analytics.run_canonical_analytics", wraps=run_canonical_analytics
        ) as analytics:
            listed = self.client.get("/api/v1/professional/patients", headers=self.headers(self.therapist))
            dossier = self.client.get(
                f"/api/v1/professional/patients/{self.patient.id}/dossier",
                headers=self.headers(self.therapist),
            )
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(dossier.status_code, 200, dossier.text)
        risk.assert_not_called()
        analytics.assert_not_called()

        rows = {row["id"]: row for row in listed.json()}
        self.assertEqual(set(rows), {str(self.patient.id), str(self.empty.id)})
        summary = rows[str(self.patient.id)]
        self.assertEqual(summary["latest_alert_level"], 3)
        self.assertEqual(summary["latest_structural_score"], 0.37)
        self.assertEqual(summary["latest_confidence_band"], "stable")
        mood = self._mood(summary["longitudinal"])
        self.assertEqual(mood["band"], "unstable")
        self.assertEqual(mood["change"], 2.5)
        self.assertNotEqual(mood["band"], summary["latest_alert_level"])
        self.assertNotEqual(mood["band"], summary["latest_confidence_band"])
        self.assertIsNone(self._feature(summary["longitudinal"], "sleep_hours")["change"])
        self.assertEqual(summary["longitudinal"]["limits"], [CHANGE_IS_NOT_RISK])

        empty = rows[str(self.empty.id)]
        self.assertIsNone(empty["latest_alert_level"])
        self.assertEqual(empty["longitudinal"]["baseline"]["status"], "insufficient_data")
        self.assertIsNone(empty["longitudinal"]["baseline"]["baseline"])
        self.assertEqual(empty["longitudinal"]["changes"], [])
        self.assertNotIn('"change": 0', listed.text)
        self.assertNotIn('"change":0', listed.text)

        body = dossier.json()
        self.assertEqual(body["current_risk"]["alert_level"], 3)
        self.assertEqual(body["patient"]["latest_alert_level"], 3)
        dossier_mood = self._mood(body["patient"]["longitudinal"])
        self.assertEqual(dossier_mood["signal_id"], str(self.mood.id))
        self.assertEqual(dossier_mood["band"], "unstable")
        self.assertNotIn("alert_level", dossier_mood)
        self.assertEqual(body["patient"]["longitudinal"]["baseline"]["baseline"]["data_coverage"], 0.5)
        self.assertIsNone(self._feature(body["patient"]["longitudinal"], "sleep_hours")["change"])
        self.assertNotIn(str(self.other_signal.id), dossier.text)

        supervised = self.client.get(
            f"/api/v1/professional/patients/{self.patient.id}/dossier",
            headers=self.headers(self.supervisor),
        )
        self.assertEqual(supervised.status_code, 200, supervised.text)
        self.assertEqual(self._mood(supervised.json()["patient"]["longitudinal"])["band"], "unstable")
        self.assertEqual(supervised.json()["current_risk"]["alert_level"], 3)

    def test_unassigned_therapist_and_admin_cannot_read_change_signals(self):
        denied = self.client.get(
            f"/api/v1/professional/patients/{self.patient.id}/dossier",
            headers=self.headers(self.other_therapist),
        )
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn(str(self.mood.id), denied.text)

        outsider_list = self.client.get(
            "/api/v1/professional/patients",
            headers=self.headers(self.other_therapist),
        )
        self.assertEqual(outsider_list.status_code, 200, outsider_list.text)
        self.assertEqual(outsider_list.json(), [])
        self.assertNotIn(str(self.mood.id), outsider_list.text)

        admin_list = self.client.get("/api/v1/professional/patients", headers=self.headers(self.admin))
        self.assertEqual(admin_list.status_code, 200, admin_list.text)
        admin_rows = {row["id"]: row for row in admin_list.json()}
        self.assertIn(str(self.patient.id), admin_rows)
        self.assertIsNone(admin_rows[str(self.patient.id)]["longitudinal"])
        self.assertIsNone(admin_rows[str(self.patient.id)]["latest_alert_level"])
        self.assertNotIn(str(self.mood.id), admin_list.text)
        self.assertNotIn("unstable", admin_list.text)

        admin_dossier = self.client.get(
            f"/api/v1/professional/patients/{self.patient.id}/dossier",
            headers=self.headers(self.admin),
        )
        self.assertEqual(admin_dossier.status_code, 403)
        self.assertNotIn(str(self.mood.id), admin_dossier.text)

    def _feature(self, longitudinal, feature):
        return next(row for row in longitudinal["changes"] if row["feature"] == feature)

    def _mood(self, longitudinal):
        return self._feature(longitudinal, "mood")


if __name__ == "__main__":
    unittest.main()
