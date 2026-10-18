import os
import unittest
import uuid
from datetime import datetime, timezone

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Consent, User
from app.models_vnext import ChangeSignal, ChangeSignalEmbedding
from app.services import change_signal_embeddings as cse


class ChangeSignalEmbeddingWriterTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

        Base.metadata.create_all(
            bind=self.engine,
            tables=[User.__table__, Consent.__table__, ChangeSignal.__table__, ChangeSignalEmbedding.__table__],
        )
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.user = User(
            id=uuid.uuid4(),
            email=f"p-{uuid.uuid4().hex[:8]}@example.test",
            display_name="P",
            hashed_password="x",
            role="patient",
            is_active=True,
        )
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _signal(self, feature="mood"):
        row = ChangeSignal(
            id=uuid.uuid4(),
            user_id=self.user.id,
            feature=feature,
            change_value=1.2,
            band="moderate",
            uncertainty={},
            evidence_refs=[],
            contradictions=[],
            algorithm_version="canonical-structural-v3",
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(row)
        self.db.commit()
        return row

    def _grant(self):
        row = Consent(
            user_id=self.user.id,
            consent_type="linguistic_analysis",
            granted=True,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def test_no_write_without_linguistic_grant(self):
        self._signal()
        self.assertEqual(cse.embed_change_signals(self.db, self.user.id), 0)
        self.assertEqual(self.db.query(ChangeSignalEmbedding).count(), 0)

    def test_no_write_when_inactive(self):
        self._grant()
        self.user.is_active = False
        self.db.commit()
        self._signal()
        self.assertEqual(cse.embed_change_signals(self.db, self.user.id), 0)

    def test_writes_fingerprint_with_consent_id(self):
        grant = self._grant()
        self._signal("mood")
        n = cse.embed_change_signals(self.db, self.user.id)
        self.assertEqual(n, 1)
        row = self.db.query(ChangeSignalEmbedding).one()
        self.assertEqual(row.consent_id, grant.id)
        self.assertEqual(row.purpose, "linguistic_analysis")
        self.assertEqual(len(row.embedding), 16)
        self.assertEqual(row.provider, "local_deterministic")

    def test_skips_chemsex_crisis_features(self):
        self._grant()
        self._signal("chemsex_days")
        self._signal("crisis_flag")
        self.assertEqual(cse.embed_change_signals(self.db, self.user.id), 0)

    def test_idempotent_per_signal(self):
        self._grant()
        self._signal("sleep_hours")
        self.assertEqual(cse.embed_change_signals(self.db, self.user.id), 1)
        self.assertEqual(cse.embed_change_signals(self.db, self.user.id), 0)


if __name__ == "__main__":
    unittest.main()
