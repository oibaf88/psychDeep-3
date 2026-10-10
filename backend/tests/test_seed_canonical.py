"""The demo seed populates the canonical pipeline, so demo screens agree."""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import User
from app.models_vnext import BaselineVersion, ChangeSignal, Observation
from app.seed import seed_demo_data
from app.services.longitudinal_read import longitudinal_state


class SeedCanonicalTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(self.engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=OFF")

        import app.models  # noqa: F401
        import app.models_vnext  # noqa: F401

        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_demo_patient_has_canonical_observations_baseline_and_comparison(self):
        seed_demo_data(self.db)
        patient = self.db.query(User).filter(User.email == "patient@demo.psychapp.example.com").one()
        self.assertEqual(self.db.query(Observation).filter(Observation.user_id == patient.id).count(), 28 * 4)
        self.assertEqual(self.db.query(BaselineVersion).filter(BaselineVersion.user_id == patient.id).count(), 1)
        self.assertGreater(self.db.query(ChangeSignal).filter(ChangeSignal.user_id == patient.id).count(), 0)
        self.assertEqual(longitudinal_state(self.db, patient.id)["summary"]["status"], "calculated")

    def test_seed_is_idempotent(self):
        seed_demo_data(self.db)
        seed_demo_data(self.db)
        self.assertEqual(self.db.query(BaselineVersion).count(), 1)


if __name__ == "__main__":
    unittest.main()
