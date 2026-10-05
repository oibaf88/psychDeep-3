"""Weekly review keeps ChangeSignal apart from RiskAssessment.

A missing change is insufficient_data / null. It is not zero and it is not
the alert level. Other roles cannot read the patient review.
"""
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.models_vnext  # noqa: F401
from app.database import Base, get_db
from app.models import RiskAssessment, User
from app.models_vnext import BaselineVersion, ChangeSignal
from app.routers import vnext
from app.security import create_access_token
from app.services.longitudinal_read import CHANGE_IS_NOT_RISK

NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)


class WeeklyReviewSeparationTests(unittest.TestCase):
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
        self.therapist = self.user("therapist", "Terapeuta")
        self.supervisor = self.user("supervisor", "Supervisor")
        self.admin = self.user("admin_clinical", "Admin")
        self.assessment = RiskAssessment(
            user_id=self.patient.id,
            alert_level=4,
            triggering_rules=["N4_demo"],
            input_signals={"structural_score": 0.91, "confidence_band": "stable"},
            input_facts={},
            assessment_reason="Evaluación de riesgo distinta del cambio.",
            model_version="risk-engine-v1",
            calculation_trace={},
            calculated_at=NOW,
        )
        self.db.add(self.assessment)
        baseline = BaselineVersion(
            user_id=self.patient.id,
            feature_key=None,
            window_start=NOW - timedelta(days=21),
            window_end=NOW,
            stats={"mood": {"n": 2, "mean": 5}},
            exclusions=[],
            stability="partial",
            data_coverage=0.25,
            status="provisional",
            algorithm_version="canonical-structural-v1",
            created_at=NOW,
        )
        self.db.add(baseline)
        self.db.flush()
        self.signal = ChangeSignal(
            user_id=self.patient.id,
            feature="mood",
            window_start=NOW - timedelta(days=7),
            window_end=NOW,
            change_value=None,
            band="insufficient_data",
            uncertainty={"reason": "insufficient_baseline_or_recent", "baseline_n": 2, "recent_n": 0},
            evidence_refs=[],
            contradictions=[],
            baseline_version_id=baseline.id,
            algorithm_version="canonical-structural-v1",
            created_at=NOW,
        )
        self.db.add(self.signal)
        self.db.commit()

        app = FastAPI()
        app.include_router(vnext.router)

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

    def headers(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}

    def test_weekly_review_keeps_a_missing_change_apart_from_the_alert(self):
        response = self.client.get("/api/v1/review/weekly", headers=self.headers(self.patient))
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["safety"]["alert_level"], 4)
        self.assertEqual(body["safety"]["assessment_id"], str(self.assessment.id))
        self.assertEqual(set(body["safety"]), {"alert_level", "assessment_id"})

        longitudinal = body["longitudinal"]
        self.assertEqual(longitudinal["limits"], [CHANGE_IS_NOT_RISK])
        self.assertNotIn("alert_level", longitudinal)
        self.assertEqual(longitudinal["baseline"]["status"], "provisional")
        mood = next(row for row in longitudinal["changes"] if row["feature"] == "mood")
        self.assertEqual(mood["band"], "insufficient_data")
        self.assertIsNone(mood["change"])
        self.assertNotIn("alert_level", mood)
        self.assertNotEqual(mood["band"], body["safety"]["alert_level"])
        self.assertNotEqual(mood["band"], "stable")
        self.assertNotIn('"change": 0', response.text)
        self.assertNotIn('"change":0', response.text)
        self.assertNotIn("sin riesgo", response.text.lower())

    def test_missing_assessment_is_not_serialised_as_level_zero(self):
        response = self.client.get("/api/v1/review/weekly", headers=self.headers(self.other))
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIsNone(body["safety"]["alert_level"])
        self.assertIsNone(body["safety"]["assessment_id"])
        self.assertEqual(body["longitudinal"]["baseline"]["status"], "insufficient_data")
        self.assertIsNone(body["longitudinal"]["baseline"]["baseline"])
        self.assertEqual(body["longitudinal"]["changes"], [])
        self.assertNotIn(str(self.signal.id), response.text)
        self.assertNotIn(str(self.assessment.id), response.text)
        self.assertNotIn('"alert_level": 0', response.text)
        self.assertNotIn('"alert_level":0', response.text)

    def test_non_patients_cannot_read_the_review(self):
        anonymous = self.client.get("/api/v1/review/weekly")
        self.assertEqual(anonymous.status_code, 401)
        self.assertNotIn(str(self.signal.id), anonymous.text)

        for user in (self.therapist, self.supervisor, self.admin):
            denied = self.client.get("/api/v1/review/weekly", headers=self.headers(user))
            self.assertEqual(denied.status_code, 403, denied.text)
            self.assertNotIn(str(self.signal.id), denied.text)
            self.assertNotIn(str(self.assessment.id), denied.text)


if __name__ == "__main__":
    unittest.main()
