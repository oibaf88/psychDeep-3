import unittest
import uuid
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.models_vnext  # noqa: F401
from app.database import Base, get_db
from app.main import app
from app.models import PatientProfessionalAssignment, User, Consent
from app.security import get_current_user


class AssignmentsApiTests(unittest.TestCase):
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
        self.db: Session = self.sessions()

        self.patient = self._user("patient")
        self.therapist = self._user("therapist")

        def override_get_db():
            session = self.sessions()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.patient
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def _user(self, role):
        row = User(
            id=uuid.uuid4(),
            email=f"{uuid.uuid4()}@example.com",
            display_name=f"Test {role}",
            hashed_password="not-used",
            role=role,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def test_therapist_can_cancel_pending_assignment(self):
        assignment = PatientProfessionalAssignment(
            patient_id=self.patient.id, professional_id=self.therapist.id, status="pending"
        )
        self.db.add(assignment)
        self.db.commit()

        # Auth as therapist
        app.dependency_overrides[get_current_user] = lambda: self.therapist

        response = self.client.post(f"/api/v1/assignments/{assignment.id}/cancel")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "canceled")

        # Verify DB
        self.db.refresh(assignment)
        self.assertEqual(assignment.status, "canceled")

    def test_patient_can_accept_assignment_and_consent_is_granted(self):
        assignment = PatientProfessionalAssignment(
            patient_id=self.patient.id, professional_id=self.therapist.id, status="pending"
        )
        self.db.add(assignment)
        self.db.commit()

        response = self.client.post(f"/api/v1/assignments/{assignment.id}/accept")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "active")

        # Check if consent was granted
        consent = (
            self.db.query(Consent)
            .filter(
                Consent.user_id == self.patient.id,
                Consent.consent_type == "professional_sharing",
                Consent.revoked_at.is_(None),
            )
            .first()
        )
        self.assertIsNotNone(consent)
        self.assertTrue(consent.granted)

    def test_revoking_consent_preserves_append_only_history(self):
        # First, accept assignment and grant consent
        assignment = PatientProfessionalAssignment(
            patient_id=self.patient.id, professional_id=self.therapist.id, status="pending"
        )
        self.db.add(assignment)
        self.db.commit()

        self.client.post(f"/api/v1/assignments/{assignment.id}/accept")

        # Now revoke the consent
        response = self.client.post(
            "/api/v1/consents",
            json={"consent_type": "professional_sharing", "granted": False},
        )
        self.assertEqual(response.status_code, 201)

        # Check history
        rows = (
            self.db.query(Consent)
            .filter(Consent.user_id == self.patient.id, Consent.consent_type == "professional_sharing")
            .order_by(Consent.granted_at, Consent.id)
            .all()
        )
        self.assertEqual(len(rows), 2)
        self.assertIsNotNone(rows[0].revoked_at)
        self.assertTrue(rows[0].granted)
        self.assertIsNone(rows[1].revoked_at)
        self.assertFalse(rows[1].granted)


if __name__ == "__main__":
    unittest.main()
