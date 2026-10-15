"""Hoy / intervention feedback writes InterventionEvent without touching risk."""
from __future__ import annotations

import unittest
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.models_vnext  # noqa: F401
from app.database import Base, get_db
from app.models import User
from app.models_vnext import InterventionEvent
from app.routers import vnext
from app.security import create_access_token


class InterventionFeedbackTests(unittest.TestCase):
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
        self.patient = self.user("patient", "Paciente Feedback")
        self.therapist = self.user("therapist", "Terapeuta")
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

    def test_patient_can_record_accepted_and_completed_usefulness(self):
        accepted = self.client.post(
            "/api/v1/feedback",
            headers=self.headers(self.patient),
            json={
                "action_id": "hoy.suggest.regular_wave",
                "state": "accepted",
                "reason": "longitudinal_adverse",
            },
        )
        self.assertEqual(accepted.status_code, 201, accepted.text)
        body = accepted.json()
        self.assertEqual(body["state"], "accepted")
        self.assertIsNone(body["usefulness"])

        completed = self.client.post(
            "/api/v1/feedback",
            headers=self.headers(self.patient),
            json={
                "action_id": "hoy.suggest.regular_wave",
                "state": "completed",
                "usefulness": 5,
                "reason": "longitudinal_adverse",
            },
        )
        self.assertEqual(completed.status_code, 201, completed.text)
        self.assertEqual(completed.json()["usefulness"], 5)

        db = self.sessions()
        try:
            rows = (
                db.query(InterventionEvent)
                .filter(InterventionEvent.user_id == self.patient.id)
                .order_by(InterventionEvent.created_at.asc())
                .all()
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].action_id, "hoy.suggest.regular_wave")
            self.assertEqual(rows[0].state, "accepted")
            self.assertEqual(rows[0].authority, "user_feedback")
            self.assertEqual(rows[0].source, "patient")
            self.assertEqual(rows[0].reason, "longitudinal_adverse")
            self.assertEqual(rows[1].state, "completed")
            self.assertEqual(rows[1].usefulness, 5)
        finally:
            db.close()

    def test_patient_can_postpone_without_usefulness(self):
        res = self.client.post(
            "/api/v1/feedback",
            headers=self.headers(self.patient),
            json={
                "action_id": "hoy.suggest.trends_explain",
                "state": "postponed",
                "reason": "calculated_explain",
            },
        )
        self.assertEqual(res.status_code, 201, res.text)
        db = self.sessions()
        try:
            row = db.query(InterventionEvent).one()
            self.assertEqual(row.state, "postponed")
            self.assertIsNone(row.usefulness)
        finally:
            db.close()

    def test_therapist_cannot_post_patient_feedback(self):
        res = self.client.post(
            "/api/v1/feedback",
            headers=self.headers(self.therapist),
            json={"action_id": "hoy.suggest.regular_wave", "state": "accepted"},
        )
        self.assertIn(res.status_code, (401, 403))

    def test_rejects_invalid_state_and_usefulness_out_of_range(self):
        bad_state = self.client.post(
            "/api/v1/feedback",
            headers=self.headers(self.patient),
            json={"action_id": "hoy.suggest.regular_wave", "state": "maybe"},
        )
        self.assertEqual(bad_state.status_code, 422)

        bad_score = self.client.post(
            "/api/v1/feedback",
            headers=self.headers(self.patient),
            json={
                "action_id": "hoy.suggest.regular_wave",
                "state": "completed",
                "usefulness": 9,
            },
        )
        self.assertEqual(bad_score.status_code, 422)


if __name__ == "__main__":
    unittest.main()
