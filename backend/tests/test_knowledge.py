import unittest
import uuid
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.models_vnext import KnowledgeItem
from app.security import get_current_user


class KnowledgeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.Session()
        self.user = User(
            id=uuid.uuid4(),
            email="admin@example.com",
            display_name="Admin",
            role="admin_clinical",
            hashed_password="x",
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

    @staticmethod
    def payload(version="v1", contraindications=None):
        return {
            "topic": "regulacion",
            "population": "adultos",
            "objective": "reducir activacion",
            "locale": "es-ES",
            "evidence_level": "consenso revisado",
            "contraindications": contraindications or [],
            "content": "Contenido sintético suficientemente largo para validar el registro.",
            "content_version": version,
            "review_due": (date.today() + timedelta(days=90)).isoformat(),
            "source_ref": "https://example.invalid/evidence",
        }

    def test_non_admin_roles_cannot_create_or_approve(self):
        for role in ("patient", "therapist", "supervisor"):
            with self.subTest(role=role):
                self.user.role = role
                self.db.commit()
                created = self.client.post("/api/v1/knowledge", json=self.payload())
                self.assertEqual(created.status_code, 403)
                approved = self.client.post(f"/api/v1/knowledge/{uuid.uuid4()}/approve")
                self.assertEqual(approved.status_code, 403)

    def test_creation_is_always_draft_and_approval_retires_predecessor(self):
        first = self.client.post("/api/v1/knowledge", json=self.payload("v1"))
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["status"], "draft")
        first_id = first.json()["id"]
        self.assertEqual(self.client.post(f"/api/v1/knowledge/{first_id}/approve").status_code, 200)

        second = self.client.post("/api/v1/knowledge", json=self.payload("v2"))
        second_id = second.json()["id"]
        self.assertEqual(self.client.post(f"/api/v1/knowledge/{second_id}/approve").status_code, 200)

        self.assertEqual(self.db.get(KnowledgeItem, uuid.UUID(first_id)).status, "retired")
        self.assertEqual(self.db.get(KnowledgeItem, uuid.UUID(second_id)).status, "active")

    def test_targeted_retrieval_excludes_contraindicated_content(self):
        created = self.client.post(
            "/api/v1/knowledge", json=self.payload("v1", ["mania"])
        ).json()
        self.client.post(f"/api/v1/knowledge/{created['id']}/approve")
        self.user.role = "therapist"
        self.db.commit()

        base_params = {
            "population": "adultos",
            "objective": "reducir activacion",
            "topic": "regulacion",
            "locale": "es-ES",
        }
        allowed = self.client.get("/api/v1/knowledge/retrieve", params=base_params)
        blocked = self.client.get(
            "/api/v1/knowledge/retrieve",
            params={**base_params, "contraindication": "mania"},
        )
        wrong_population = self.client.get(
            "/api/v1/knowledge/retrieve",
            params={**base_params, "population": "adolescentes"},
        )

        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(len(allowed.json()), 1)
        self.assertEqual(blocked.json(), [])
        self.assertEqual(wrong_population.json(), [])

    def test_blank_or_oversized_records_are_rejected(self):
        blank = self.payload()
        blank["objective"] = "   "
        oversized = self.payload()
        oversized["content"] = "x" * 20_001
        self.assertEqual(self.client.post("/api/v1/knowledge", json=blank).status_code, 422)
        self.assertEqual(self.client.post("/api/v1/knowledge", json=oversized).status_code, 422)


if __name__ == "__main__":
    unittest.main()
