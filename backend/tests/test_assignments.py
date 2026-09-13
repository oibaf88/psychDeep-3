import unittest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import PatientProfessionalAssignment, User
from app.routers.assignments import request_assignment
from app.schemas import AssignmentRequestIn

class TestRequestAssignment(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock(spec=Session)
        self.patient = User(id=uuid.uuid4(), email="patient@example.com", role="patient")
        self.therapist = User(id=uuid.uuid4(), email="therapist@example.com", role="therapist")
        self.admin = User(id=uuid.uuid4(), email="admin@example.com", role="admin_clinical")
        self.payload = AssignmentRequestIn(patient_email="patient@example.com")

    def test_admin_cannot_request_assignment(self):
        """Admin clinical users should not be allowed to request assignments."""
        with self.assertRaises(HTTPException) as context:
            request_assignment(self.payload, self.db, self.admin)
        self.assertEqual(context.exception.status_code, 403)
        self.assertIn("admin_clinical manages assignments via overrides", context.exception.detail)

    def test_patient_not_found(self):
        """Should raise 404 if the patient with the requested email is not found."""
        self.db.query.return_value.filter.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as context:
            request_assignment(self.payload, self.db, self.therapist)
        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "No patient with that email")

    @patch("app.routers.assignments._enrich")
    def test_existing_assignment(self, mock_enrich):
        """If a pending, active, or paused assignment already exists, it should be returned."""
        # Setup db.query to return the patient first, then the existing assignment
        self.db.query.return_value.filter.return_value.first.side_effect = [
            self.patient,
            PatientProfessionalAssignment(patient_id=self.patient.id, professional_id=self.therapist.id, status="pending")
        ]
        mock_enrich.return_value = "enriched_assignment"

        result = request_assignment(self.payload, self.db, self.therapist)

        self.assertEqual(result, "enriched_assignment")
        mock_enrich.assert_called_once()
        self.db.add.assert_not_called()

    @patch("app.routers.assignments.audit.log")
    @patch("app.routers.assignments._enrich")
    def test_new_assignment_created(self, mock_enrich, mock_audit_log):
        """If no assignment exists, a new pending assignment should be created and logged."""
        # Setup db.query to return the patient first, then None for existing assignment
        self.db.query.return_value.filter.return_value.first.side_effect = [
            self.patient,
            None  # No existing assignment
        ]
        mock_enrich.return_value = "new_enriched_assignment"

        result = request_assignment(self.payload, self.db, self.therapist)

        self.assertEqual(result, "new_enriched_assignment")
        self.db.add.assert_called_once()
        self.db.commit.assert_called_once()
        self.db.refresh.assert_called_once()

        # Verify the assignment that was added to DB
        added_assignment = self.db.add.call_args[0][0]
        self.assertEqual(added_assignment.patient_id, self.patient.id)
        self.assertEqual(added_assignment.professional_id, self.therapist.id)
        self.assertEqual(added_assignment.status, "pending")

        mock_audit_log.assert_called_once_with(
            self.db,
            actor_id=self.therapist.id,
            actor_role=self.therapist.role,
            action="assignment_requested",
            entity_type="assignment",
            entity_id=added_assignment.id,
            extra={"patient_id": str(self.patient.id)}
        )

if __name__ == "__main__":
    unittest.main()
