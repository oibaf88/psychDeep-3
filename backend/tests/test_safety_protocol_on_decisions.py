"""Each risk decision records the safety pack that governed it (G3).

``safety-protocol-v1`` used to be visible only on
``GET /api/v1/safety-plan/resources``. A stored RiskAssessment or
ProfessionalAlert did not say which crisis resources and fixed LEVEL3/LEVEL4
copy were in force, so a later pack change would make an old crisis
response impossible to reproduce. The version is now written into the
decision's ``calculation_trace`` and the alert's ``related_signals``.
It is a label only: levels, rules and thresholds are unchanged, and
assessments written before this stay null rather than being relabelled.
"""
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
import app.models_vnext  # noqa: F401
from app.content.safety_resources import SAFETY_PROTOCOL_VERSION
from app.database import Base, get_db
from app.models import ProfessionalAlert, RiskAssessment, User
from app.routers import vnext
from app.security import create_access_token
from app.services import risk_engine
from test_risk_traceability import _CalculationHarness, _linguistic, _structural


class DecisionTraceCarriesProtocolTests(_CalculationHarness, unittest.TestCase):
    def test_stable_decision_names_the_safety_pack(self):
        decision = self._calculate()
        self.assertEqual(decision.level, 0)
        self.assertEqual(decision.calculation_trace["engine"]["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)

    def test_crisis_decision_names_the_same_pack_and_keeps_its_level(self):
        fact = {"id": str(uuid.uuid4()), "category": "planning", "created_at": datetime.utcnow().isoformat()}
        decision = self._calculate(
            structural=_structural(score=0.1, band="unstable"),
            linguistic=_linguistic(ideation=True),
            n4=[fact],
            persistence=(1, 3, 5),
        )
        self.assertEqual(decision.level, 4)
        self.assertEqual(decision.triggering_rules, ["N4_declaracion_ideacion_o_plan"])
        self.assertEqual(decision.calculation_trace["engine"]["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)


def _sqlite_sessions():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _user(db, role="patient"):
    row = User(email=f"{uuid.uuid4()}@example.com", display_name="Paciente", hashed_password="x", role=role)
    db.add(row)
    db.commit()
    return row


def _decision(level, rules):
    return risk_engine.RiskDecision(
        level=level,
        triggering_rules=rules,
        reason="Decisión determinista de prueba.",
        input_signals={"structural_score": 0.2, "confidence_band": "unstable"},
        input_facts={},
        calculation_trace={
            "schema_version": "risk-explanation-v1",
            # The engine stamps the pack in calculate_risk_level (tested above);
            # here the alert path must stamp it on its own.
            "engine": {"version": risk_engine.MODEL_VERSION},
            "conclusion": {"selected_rule_code": rules[0]},
        },
    )


class PersistedDecisionTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.sessions = _sqlite_sessions()
        self.db = self.sessions()
        self.patient = _user(self.db)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _persist(self, decision):
        with patch.object(risk_engine, "calculate_risk_level", return_value=decision):
            return risk_engine.run_and_persist(self.db, self.patient.id, notify=False)

    def test_level_three_alert_and_its_refresh_both_record_the_pack(self):
        first = self._persist(_decision(3, ["N3_demo"]))
        alert = self.db.get(ProfessionalAlert, first.generated_alert_id)
        self.assertEqual(alert.alert_level, 3)
        self.assertEqual(alert.related_signals["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)
        self.assertEqual(alert.related_signals["triggering_rules"], ["N3_demo"])

        second = self._persist(_decision(3, ["N3_demo"]))
        self.assertEqual(second.generated_alert_id, alert.id)
        self.db.refresh(alert)
        self.assertEqual(alert.related_signals["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)
        self.assertEqual(alert.related_signals["assessment_id"], str(second.id))
        self.assertEqual(self.db.query(ProfessionalAlert).count(), 1)

    def test_low_level_decision_creates_no_alert(self):
        assessment = self._persist(_decision(1, ["N1_demo"]))
        self.assertEqual(assessment.alert_level, 1)
        self.assertIsNone(assessment.generated_alert_id)
        self.assertEqual(self.db.query(ProfessionalAlert).count(), 0)


class StateReadsRecordedPackTests(unittest.TestCase):
    def setUp(self):
        self.engine, self.sessions = _sqlite_sessions()
        self.db = self.sessions()
        self.patient = _user(self.db)
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
        self.headers = {"Authorization": f"Bearer {create_access_token(self.patient.id, 'patient')}"}

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def _assessment(self, trace):
        self.db.add(
            RiskAssessment(
                user_id=self.patient.id,
                alert_level=2,
                triggering_rules=["N2_demo"],
                input_signals={},
                input_facts={},
                assessment_reason="demo",
                model_version=risk_engine.MODEL_VERSION,
                calculation_trace=trace,
                calculated_at=datetime(2026, 10, 19, 8, tzinfo=timezone.utc).replace(tzinfo=None),
            )
        )
        self.db.commit()

    def _safety(self):
        response = self.client.get("/api/v1/state", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["safety"]

    def test_state_returns_the_pack_recorded_on_the_decision(self):
        self._assessment({"engine": {"safety_protocol_version": SAFETY_PROTOCOL_VERSION}})
        safety = self._safety()
        self.assertEqual(safety["alert_level"], 2)
        self.assertEqual(safety["safety_protocol_version"], SAFETY_PROTOCOL_VERSION)

    def test_older_decision_without_a_recorded_pack_stays_null(self):
        self._assessment({"engine": {"version": "risk-engine-v1.5"}})
        safety = self._safety()
        self.assertEqual(safety["alert_level"], 2)
        self.assertIsNone(safety["safety_protocol_version"])

    def test_no_assessment_yet_is_null_not_a_default_pack(self):
        safety = self._safety()
        self.assertIsNone(safety["alert_level"])
        self.assertIsNone(safety["safety_protocol_version"])


if __name__ == "__main__":
    unittest.main()
