import unittest
import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import Consent, User
from app.services.consent import is_granted, VALID_PURPOSES

class ConsentsApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db: Session = self.sessions()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        self.user = User(
            id=uuid.uuid4(),
            email="patient@example.com",
            hashed_password="fake",
            role="patient",
            display_name="Test Patient"
        )
        self.db.add(self.user)
        self.db.commit()

        # To authenticate, we can either mock get_current_user or just use dependency override
        from app.security import get_current_user
        def override_get_current_user():
            return self.user

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        self.client = TestClient(app)

    def tearDown(self):
        self.db.close()
        app.dependency_overrides.clear()

    def test_list_consents_empty(self):
        response = self.client.get("/api/v1/consents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_set_and_list_consent(self):
        payload = {"consent_type": "data_processing", "granted": True}
        response = self.client.post("/api/v1/consents", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["consent_type"], "data_processing")
        self.assertTrue(data["granted"])
        self.assertIn("id", data)

        response = self.client.get("/api/v1/consents")
        self.assertEqual(len(response.json()), 1)

    def test_revoke_consent_maintains_history(self):
        # 1. Grant
        self.client.post("/api/v1/consents", json={"consent_type": "research", "granted": True})

        # Verify granted
        self.assertTrue(is_granted(self.db, self.user.id, "research"))

        # 2. Revoke
        self.client.post("/api/v1/consents", json={"consent_type": "research", "granted": False})

        # Verify not granted
        self.assertFalse(is_granted(self.db, self.user.id, "research"))

        # Verify history has 2 rows
        response = self.client.get("/api/v1/consents")
        self.assertEqual(len(response.json()), 2)

        # Look at the db layer
        consents = self.db.query(Consent).filter_by(user_id=self.user.id).order_by(Consent.granted_at).all()
        self.assertEqual(len(consents), 2)
        # First one should be revoked
        self.assertIsNotNone(consents[0].revoked_at)
        self.assertTrue(consents[0].granted)
        # Second one is the active revocation
        self.assertIsNone(consents[1].revoked_at)
        self.assertFalse(consents[1].granted)

    def test_invalid_consent_type(self):
        payload = {"consent_type": "invalid_purpose", "granted": True}
        response = self.client.post("/api/v1/consents", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent_type must be one of", response.json()["detail"])

    def test_is_granted_service_method(self):
        # Should be false initially
        self.assertFalse(is_granted(self.db, self.user.id, "professional_sharing"))

        # Add manual consent in DB
        consent = Consent(user_id=self.user.id, consent_type="professional_sharing", granted=True)
        self.db.add(consent)
        self.db.commit()

        self.assertTrue(is_granted(self.db, self.user.id, "professional_sharing"))
