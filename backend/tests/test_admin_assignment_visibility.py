"""Clinical admins can see pending and done assignment links, not the chart."""
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
from app.models import PatientProfessionalAssignment, RiskAssessment, User
from app.routers import assignments, professional
from app.security import create_access_token


class AdminAssignmentVisibilityTests(unittest.TestCase):
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
        self.patient = self.user("patient", "Paciente Con Vínculos")
        self.unlinked = self.user("patient", "Paciente Sin Vínculos")
        self.other_patient = self.user("patient", "Otra Persona")
        self.therapist = self.user("therapist", "Dra. Activa")
        self.other_therapist = self.user("therapist", "Dr. Pendiente")
        self.closer = self.user("therapist", "Dra. Cierre")
        self.supervisor = self.user("supervisor", "Supervisor")
        self.admin = self.user("admin_clinical", "Admin Clínico")
        self.db.add_all([
            PatientProfessionalAssignment(
                patient_id=self.patient.id, professional_id=self.therapist.id, status="active"
            ),
            PatientProfessionalAssignment(
                patient_id=self.patient.id, professional_id=self.other_therapist.id, status="pending"
            ),
            PatientProfessionalAssignment(
                patient_id=self.patient.id, professional_id=self.closer.id, status="ended"
            ),
            PatientProfessionalAssignment(
                patient_id=self.other_patient.id, professional_id=self.closer.id, status="active"
            ),
        ])
        self.db.add(
            RiskAssessment(
                user_id=self.patient.id,
                alert_level=3,
                triggering_rules=["N3_demo"],
                input_signals={"structural_score": 0.91, "confidence_band": "unstable"},
                input_facts={},
                assessment_reason="CLINICAL-SECRET-REASON",
                model_version="risk-engine-v1",
                calculation_trace={},
            )
        )
        self.db.commit()

        app = FastAPI()
        app.include_router(assignments.router)
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

    def headers(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}

    def test_admin_roster_lists_pending_and_done_without_clinical_fields(self):
        response = self.client.get("/api/v1/professional/patients", headers=self.headers(self.admin))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("CLINICAL-SECRET-REASON", response.text)
        self.assertNotIn("unstable", response.text)
        self.assertNotIn("roster", response.text)

        rows = {row["id"]: row for row in response.json()}
        linked = rows[str(self.patient.id)]
        self.assertIsNone(linked["latest_alert_level"])
        self.assertIsNone(linked["longitudinal"])
        self.assertEqual(linked["checkin_count"], 0)
        self.assertEqual(linked["assignment_status"], "pending")
        by_status = {item["status"]: item for item in linked["assignments"]}
        self.assertEqual(set(by_status), {"pending", "active", "ended"})
        self.assertEqual(by_status["pending"]["professional_display_name"], "Dr. Pendiente")
        self.assertEqual(by_status["active"]["professional_display_name"], "Dra. Activa")
        self.assertEqual(by_status["ended"]["professional_display_name"], "Dra. Cierre")
        self.assertNotIn("alert_level", by_status["active"])

        unlinked = rows[str(self.unlinked.id)]
        self.assertEqual(unlinked["assignment_status"], "none")
        self.assertEqual(unlinked["assignments"], [])
        self.assertIsNone(unlinked["latest_alert_level"])

    def test_supervisor_keeps_clinical_read_and_sees_both_assignment_groups(self):
        response = self.client.get("/api/v1/professional/patients", headers=self.headers(self.supervisor))
        self.assertEqual(response.status_code, 200, response.text)
        rows = {row["id"]: row for row in response.json()}
        linked = rows[str(self.patient.id)]
        self.assertEqual(linked["latest_alert_level"], 3)
        self.assertEqual({item["status"] for item in linked["assignments"]}, {"pending", "active", "ended"})

    def test_admin_can_filter_one_patient_into_pending_and_done(self):
        pending = self.client.get(
            f"/api/v1/assignments/mine?patient_id={self.patient.id}&group=pending",
            headers=self.headers(self.admin),
        )
        done = self.client.get(
            f"/api/v1/assignments/mine?patient_id={self.patient.id}&group=done",
            headers=self.headers(self.admin),
        )
        self.assertEqual(pending.status_code, 200, pending.text)
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual([row["status"] for row in pending.json()], ["pending"])
        self.assertEqual(sorted(row["status"] for row in done.json()), ["active", "ended"])
        self.assertNotIn("CLINICAL-SECRET-REASON", pending.text + done.text)

        rejected = self.client.get(
            "/api/v1/assignments/mine?group=neither",
            headers=self.headers(self.admin),
        )
        self.assertEqual(rejected.status_code, 400)

    def test_patient_and_therapist_cannot_read_another_persons_links(self):
        stolen = self.client.get(
            f"/api/v1/assignments/mine?patient_id={self.other_patient.id}",
            headers=self.headers(self.patient),
        )
        self.assertEqual(stolen.status_code, 200, stolen.text)
        self.assertEqual({row["patient_id"] for row in stolen.json()}, {str(self.patient.id)})
        self.assertNotIn("Otra Persona", stolen.text)
        self.assertEqual(len(stolen.json()), 3)

        outsider = self.client.get(
            f"/api/v1/assignments/mine?patient_id={self.patient.id}&group=done",
            headers=self.headers(self.other_therapist),
        )
        self.assertEqual(outsider.status_code, 200, outsider.text)
        self.assertEqual(outsider.json(), [])
        self.assertNotIn(self.therapist.email, outsider.text)

        own_pending = self.client.get(
            f"/api/v1/assignments/mine?patient_id={self.patient.id}&group=pending",
            headers=self.headers(self.other_therapist),
        )
        self.assertEqual(own_pending.status_code, 200, own_pending.text)
        self.assertEqual([row["professional_id"] for row in own_pending.json()], [str(self.other_therapist.id)])

        blocked = self.client.get("/api/v1/assignments/all", headers=self.headers(self.patient))
        self.assertEqual(blocked.status_code, 403)

        roster = self.client.get("/api/v1/professional/patients", headers=self.headers(self.therapist))
        self.assertEqual(roster.status_code, 200, roster.text)
        self.assertEqual([row["id"] for row in roster.json()], [str(self.patient.id)])
        self.assertEqual(roster.json()[0]["assignments"], [])
        self.assertNotIn(self.other_therapist.email, roster.text)
        self.assertNotIn(str(self.other_patient.id), roster.text)

    def test_admin_still_cannot_open_the_dossier(self):
        response = self.client.get(
            f"/api/v1/professional/patients/{self.patient.id}/dossier",
            headers=self.headers(self.admin),
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("CLINICAL-SECRET-REASON", response.text)


if __name__ == "__main__":
    unittest.main()
