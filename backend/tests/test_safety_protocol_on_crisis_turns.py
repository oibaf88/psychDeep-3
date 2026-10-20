"""LEVEL3/LEVEL4 chat turns and alert notices name the safety pack (G3).

The RiskAssessment and ProfessionalAlert already record which server-owned
safety pack (``SAFETY_PROTOCOL_VERSION``) governed a decision. The stored
assistant turn that carried the fixed LEVEL3/LEVEL4 copy and crisis
resources, and the notices sent for that alert, did not. After a pack change
nobody could tell from the turn or the notice which copy and resources the
person had actually been shown. They now carry the label too.

It is a label only: alert levels, rules, thresholds, phone numbers and the
fixed wording are unchanged. Level 0-2 replies and non-alert notices stay
null, and rows written before this stay null rather than being relabelled.
"""
import unittest
import uuid
from datetime import datetime
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.models_vnext  # noqa: F401
from app.content.safety_resources import (
    AGENT1_OUTPUT_BLOCKED_MESSAGE,
    CRISIS_RESOURCES,
    LEVEL3_PATIENT_MESSAGE,
    LEVEL3_PATIENT_MESSAGE_WITH_PROFESSIONAL,
    LEVEL4_PATIENT_MESSAGE,
    SAFETY_PROTOCOL_VERSION,
)
from app.database import Base, get_db
from app.models import ChatMessage, Notification, PatientProfessionalAssignment, User
from app.routers import chat, notifications as notifications_router
from app.schemas import ChatOut, PatientChatMessageOut
from app.security import create_access_token
from app.services import notifications, risk_engine
from test_agent1_output_validation import _ReplyHarness
from test_safety_protocol_on_decisions import _decision


class CrisisTurnCarriesPackTests(_ReplyHarness, unittest.TestCase):
    def test_level4_turn_and_reply_name_the_pack_and_keep_resources(self):
        reply, _, assistant = self._reply(4, "Estoy aquí contigo.")
        self.assertEqual(reply["ui_mode"], "crisis")
        self.assertEqual(reply["resources"], CRISIS_RESOURCES)
        self.assertTrue(reply["reply"].endswith(LEVEL4_PATIENT_MESSAGE))
        self.assertEqual(reply["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)
        self.assertEqual(len(assistant), 1)
        self.assertEqual(assistant[0].safety_protocol_version, SAFETY_PROTOCOL_VERSION)
        self.assertEqual(ChatOut(**reply).safety_protocol_version, SAFETY_PROTOCOL_VERSION)

    def test_level4_turn_names_the_pack_when_model_prose_was_withheld(self):
        reply, audits, assistant = self._reply(4, "Tu nivel de riesgo es alto. Llama al 900 000 000.")
        self.assertEqual(reply["reply"], LEVEL4_PATIENT_MESSAGE)
        self.assertEqual(len(audits), 1)
        self.assertEqual(assistant[0].safety_protocol_version, SAFETY_PROTOCOL_VERSION)
        # Template-only turn: no model provenance, but the pack is still named.
        self.assertIsNone(getattr(assistant[0], "model", None))

    def test_level3_turn_names_the_pack_with_and_without_professional(self):
        for has_professional, fixed in ((False, LEVEL3_PATIENT_MESSAGE), (True, LEVEL3_PATIENT_MESSAGE_WITH_PROFESSIONAL)):
            with self.subTest(has_professional=has_professional):
                reply, _, assistant = self._reply(3, "Te leo.", has_professional=has_professional)
                self.assertEqual(reply["ui_mode"], "support")
                self.assertIsNone(reply["resources"])
                self.assertTrue(reply["reply"].endswith(fixed))
                self.assertEqual(reply["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)
                self.assertEqual(assistant[0].safety_protocol_version, SAFETY_PROTOCOL_VERSION)

    def test_low_level_turns_carry_no_pack(self):
        for level, text in ((0, "Te leo. ¿Qué ha sido lo más difícil hoy?"), (2, "Tu nivel de riesgo es bajo.")):
            with self.subTest(level=level):
                reply, _, assistant = self._reply(level, text)
                self.assertEqual(reply["ui_mode"], "normal")
                self.assertIsNone(reply["safety_protocol_version"])
                self.assertIsNone(assistant[0].safety_protocol_version)
        # The level-2 reply above was withheld; the server-owned support copy
        # is not the LEVEL3/LEVEL4 pack and must not be labelled as such.
        self.assertEqual(reply["reply"], AGENT1_OUTPUT_BLOCKED_MESSAGE)


def _sqlite_sessions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _user(db, role):
    row = User(email=f"{uuid.uuid4()}@example.com", display_name=role.title(), hashed_password="x", role=role)
    db.add(row)
    db.commit()
    return row


class _SqliteCase(unittest.TestCase):
    def setUp(self):
        self.engine, self.sessions = _sqlite_sessions()
        self.db = self.sessions()
        self.patient = _user(self.db, "patient")
        self.professional = _user(self.db, "therapist")
        self.db.add(
            PatientProfessionalAssignment(
                patient_id=self.patient.id, professional_id=self.professional.id, status="active"
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()


class AlertNoticesCarryPackTests(_SqliteCase):
    def _persist(self, level, rules):
        with (
            patch.object(risk_engine, "calculate_risk_level", return_value=_decision(level, rules)),
            patch.object(notifications, "_send_email", return_value=False),
        ):
            return risk_engine.run_and_persist(self.db, self.patient.id, notify=True)

    def test_every_notice_for_a_level4_alert_names_the_pack(self):
        assessment = self._persist(4, ["N4_demo"])
        self.assertEqual(assessment.alert_level, 4)
        rows = self.db.query(Notification).all()
        # Professional in-app + professional email + patient in-app.
        self.assertEqual(
            sorted((row.recipient_type, row.channel) for row in rows),
            [("patient", "in_app"), ("professional", "email"), ("professional", "in_app")],
        )
        for row in rows:
            with self.subTest(recipient=row.recipient_type, channel=row.channel):
                self.assertEqual(row.alert_level, 4)
                self.assertEqual(row.related_alert_id, assessment.generated_alert_id)
                self.assertEqual(row.safety_protocol_version, SAFETY_PROTOCOL_VERSION)

    def test_level3_notices_name_the_pack(self):
        self._persist(3, ["N3_demo"])
        rows = self.db.query(Notification).all()
        self.assertEqual(len(rows), 3)
        self.assertEqual({row.safety_protocol_version for row in rows}, {SAFETY_PROTOCOL_VERSION})

    def test_low_level_decision_sends_no_notice(self):
        self._persist(2, ["N2_demo"])
        self.assertEqual(self.db.query(Notification).count(), 0)

    def test_memory_attention_notice_is_not_a_safety_notice(self):
        notifications.dispatch_memory_attention(
            self.db, patient_id=self.patient.id, title="Memoria clínica", body="Hay una nota nueva."
        )
        rows = self.db.query(Notification).all()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].safety_protocol_version)


class ReadsExposeRecordedPackTests(_SqliteCase):
    def setUp(self):
        super().setUp()
        app = FastAPI()
        app.include_router(chat.router)
        app.include_router(notifications_router.router)

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
        super().tearDown()

    def _headers(self, user):
        return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}

    def test_chat_history_returns_the_recorded_pack_and_null_for_older_turns(self):
        self.db.add_all(
            [
                ChatMessage(user_id=self.patient.id, role="assistant", content="antes", ui_mode="crisis"),
                ChatMessage(
                    user_id=self.patient.id, role="assistant", content="ahora", ui_mode="crisis",
                    safety_protocol_version=SAFETY_PROTOCOL_VERSION,
                ),
            ]
        )
        self.db.commit()
        response = self.client.get("/api/v1/chat/history", headers=self._headers(self.patient))
        self.assertEqual(response.status_code, 200, response.text)
        by_content = {row["content"]: row for row in response.json()}
        # A turn written before this change is not relabelled with today's pack.
        self.assertIsNone(by_content["antes"]["safety_protocol_version"])
        self.assertEqual(by_content["ahora"]["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)

    def test_professional_chat_schema_carries_the_pack(self):
        row = ChatMessage(
            id=uuid.uuid4(), user_id=self.patient.id, role="assistant", content="x", ui_mode="support",
            safety_protocol_version=SAFETY_PROTOCOL_VERSION,
        )
        row.created_at = datetime(2026, 10, 20, 8)
        self.assertEqual(PatientChatMessageOut.model_validate(row).safety_protocol_version, SAFETY_PROTOCOL_VERSION)

    def test_notification_list_returns_the_recorded_pack(self):
        with patch.object(risk_engine, "calculate_risk_level", return_value=_decision(4, ["N4_demo"])), patch.object(
            notifications, "_send_email", return_value=False
        ):
            risk_engine.run_and_persist(self.db, self.patient.id, notify=True)
        for user in (self.patient, self.professional):
            with self.subTest(role=user.role):
                response = self.client.get("/api/v1/notifications", headers=self._headers(user))
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertTrue(body)
                self.assertEqual({row["safety_protocol_version"] for row in body}, {SAFETY_PROTOCOL_VERSION})


if __name__ == "__main__":
    unittest.main()
