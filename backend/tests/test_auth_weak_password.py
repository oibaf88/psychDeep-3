import unittest
import uuid
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db, Base
from app.models import AuditLog, Consent, PasswordResetToken, SafetyPlan, User
from app.routers import auth
from app.security import hash_password

app = FastAPI()
app.include_router(auth.router)


class TestAuthWeakPassword(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We need check_same_thread=False and StaticPool for memory DB in testing
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for model in (User, Consent, SafetyPlan, PasswordResetToken, AuditLog):
            model.__table__.create(cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)

        def override_get_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

    def setUp(self):
        self.client = TestClient(app)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.query(User).delete()
        self.db.query(Consent).delete()
        self.db.query(SafetyPlan).delete()
        self.db.query(PasswordResetToken).delete()
        self.db.query(AuditLog).delete()
        self.db.commit()
        self.db.close()

    def user(self, email="user@example.com", password="ValidPassword123!"):
        user = User(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hash_password(password),
            display_name="Test User",
            is_active=True,
            role="patient"
        )
        self.db.add(user)
        self.db.commit()
        return user

    def reset_token(self, user):
        token = PasswordResetToken(
            user_id=user.id,
            token=str(uuid.uuid4()),
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        self.db.add(token)
        self.db.commit()
        return token

    def get_auth_headers(self, user):
        from app.security import create_access_token
        token = create_access_token(user.id, user.role, user.auth_version or 1)
        return {"Authorization": f"Bearer {token}"}

    def test_register_weak_password(self):
        weak_password = "a" * 80
        response = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": weak_password,
                "display_name": "Test User"
            }
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("supera el límite seguro", response.json()["detail"])

    def test_change_password_weak_password(self):
        user = self.user()
        headers = self.get_auth_headers(user)
        weak_password = "a" * 80
        response = self.client.post(
            "/api/v1/auth/change-password",
            headers=headers,
            json={
                "current_password": "ValidPassword123!",
                "new_password": weak_password
            }
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("supera el límite seguro", response.json()["detail"])

    def test_password_reset_confirm_weak_password(self):
        user = self.user()
        token = self.reset_token(user)
        weak_password = "a" * 80
        response = self.client.post(
            "/api/v1/auth/password-reset-confirm",
            json={
                "token": token.token,
                "new_password": weak_password
            }
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("supera el límite seguro", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
