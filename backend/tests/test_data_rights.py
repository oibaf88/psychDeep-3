import unittest
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import CheckIn, Consent, DiaryEntry, SafetyPlan, User
from app.routers import rights
from app.security import get_current_user
from app.services.consent import CORE_PROCESSING, is_granted


class DataRightsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db: Session = self.sessions()
        self.user = User(
            id=uuid.uuid4(),
            email="rights@example.com",
            hashed_password="fake",
            role="patient",
            display_name="Rights Patient",
        )
        self.db.add(self.user)
        self.db.add(Consent(user_id=self.user.id, consent_type=CORE_PROCESSING, granted=True))
        self.db.add(CheckIn(user_id=self.user.id, mood=5, craving=1, sleep_hours=7, self_efficacy=6, notes="ok"))
        self.db.add(DiaryEntry(user_id=self.user.id, content="Hoy bien"))
        self.db.add(SafetyPlan(user_id=self.user.id, reasons_to_live="familia"))
        self.db.commit()

        def override_get_db():
            yield self.db

        app = FastAPI()
        app.include_router(rights.router)
        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.app = app
        self.client = TestClient(app)

    def tearDown(self):
        self.app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def test_export_contains_patient_provided_data_and_not_password(self):
        response = self.client.get("/api/v1/me/data-export")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["schema"], "psychdeep-data-export-v1")
        self.assertEqual(body["account"]["email"], "rights@example.com")
        self.assertNotIn("hashed_password", body["account"])
        self.assertEqual(len(body["check_ins"]), 1)
        self.assertEqual(body["diary_entries"][0]["content"], "Hoy bien")
        self.assertIn("15", body["legal"]["gdpr_articles"])
        self.assertIn("20", body["legal"]["gdpr_articles"])

    def test_erasure_stops_processing_but_keeps_clinical_rows(self):
        response = self.client.post("/api/v1/me/erasure-request")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["hard_delete"])
        self.db.refresh(self.user)
        self.assertFalse(self.user.is_active)
        self.assertFalse(is_granted(self.db, self.user.id, CORE_PROCESSING))
        self.assertEqual(self.db.query(DiaryEntry).filter(DiaryEntry.user_id == self.user.id).count(), 1)
        self.assertEqual(self.db.query(CheckIn).filter(CheckIn.user_id == self.user.id).count(), 1)


if __name__ == "__main__":
    unittest.main()
