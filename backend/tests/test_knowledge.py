import unittest
import uuid

from fastapi import HTTPException
from app.models import KnowledgeItem, User
from app.routers import knowledge
from app.schemas import KnowledgeItemIn

class FakeSession:
    def __init__(self, existing=None):
        self.added = []
        self.existing = existing or []

    def add(self, obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass

    def query(self, model):
        return self

    def filter(self, condition):
        return self

    def all(self):
        return self.existing

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.admin = User(id=uuid.uuid4(), role="admin_clinical")
        self.patient = User(id=uuid.uuid4(), role="patient")

    def test_list_active_knowledge(self):
        item = KnowledgeItem(
            id=uuid.uuid4(),
            population_target="Test",
            clinical_objective="Test",
            content="Active content",
            version="v1",
            is_active=True
        )
        db = FakeSession(existing=[item])
        result = knowledge.list_active_knowledge(db, self.patient)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].content, "Active content")

    def test_create_knowledge_item_admin(self):
        db = FakeSession()
        payload = KnowledgeItemIn(
            population_target="Test Pop",
            clinical_objective="Test Obj",
            content="Test Content",
            evidence_level="High",
            version="v2",
            is_active=True
        )
        result = knowledge.create_knowledge_item(payload, db, self.admin)
        self.assertEqual(len(db.added), 1)
        self.assertEqual(result.population_target, "Test Pop")
        self.assertEqual(result.reviewed_by, self.admin.id)

if __name__ == "__main__":
    unittest.main()
