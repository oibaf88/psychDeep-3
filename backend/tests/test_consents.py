import unittest
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import CheckIn, Consent, DiaryEntry, User
from app.security import get_current_user
from app.services.consent import CORE_PROCESSING, is_granted


class ConsentsApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(bind=self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db: Session = self.sessions()
        self.user = User(
            id=uuid.uuid4(),
            email="patient@example.com",
            hashed_password="fake",
            role="patient",
            display_name="Test Patient",
        )
        self.db.add(self.user)
        self.db.commit()

        def override_get_db():
            yield self.db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def set_consent(self, purpose: str, granted: bool):
        return self.client.post(
            "/api/v1/consents",
            json={"consent_type": purpose, "granted": granted},
        )

    def test_revoke_consent_preserves_append_only_history(self):
        self.assertEqual(self.set_consent("research", True).status_code, 201)
        self.assertTrue(is_granted(self.db, self.user.id, "research"))
        self.assertEqual(self.set_consent("research", False).status_code, 201)
        self.assertFalse(is_granted(self.db, self.user.id, "research"))

        rows = (
            self.db.query(Consent)
            .filter(Consent.user_id == self.user.id, Consent.consent_type == "research")
            .order_by(Consent.granted_at, Consent.id)
            .all()
        )
        self.assertEqual(len(rows), 2)
        self.assertIsNotNone(rows[0].revoked_at)
        self.assertTrue(rows[0].granted)
        self.assertIsNone(rows[1].revoked_at)
        self.assertFalse(rows[1].granted)

    def test_core_revocation_blocks_all_legacy_write_routes(self):
        self.assertEqual(self.set_consent(CORE_PROCESSING, True).status_code, 201)
        self.assertEqual(self.set_consent(CORE_PROCESSING, False).status_code, 201)

        checkin = self.client.post(
            "/api/v1/checkins",
            json={"mood": 5, "craving": 2, "sleep_hours": 7, "self_efficacy": 6},
        )
        diary = self.client.post("/api/v1/diary", json={"content": "Entrada sintética"})
        chat = self.client.post("/api/v1/chat", json={"message": "Mensaje sintético"})

        self.assertEqual(checkin.status_code, 403)
        self.assertEqual(diary.status_code, 403)
        self.assertEqual(chat.status_code, 403)
        self.assertEqual(self.db.query(CheckIn).count(), 0)
        self.assertEqual(self.db.query(DiaryEntry).count(), 0)

    def test_invalid_consent_type_is_rejected(self):
        response = self.set_consent("invalid_purpose", True)
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
