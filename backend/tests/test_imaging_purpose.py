import unittest
import uuid
from types import SimpleNamespace

from fastapi import HTTPException

from app.routers.consents import set_consent
from app.schemas import ConsentIn
from app.services.consent import (
    CORE_PROCESSING,
    NEUROIMAGING_CHANGE,
    NOT_OFFERED_YET,
    VALID_PURPOSES,
    require_imaging_grant,
)


class _DenyQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class _DenyDb:
    def query(self, _model):
        return _DenyQuery()


class ImagingPurposeTests(unittest.TestCase):
    def test_imaging_is_a_known_purpose_and_not_core(self):
        self.assertIn(NEUROIMAGING_CHANGE, VALID_PURPOSES)
        self.assertNotEqual(NEUROIMAGING_CHANGE, CORE_PROCESSING)
        self.assertIn(NEUROIMAGING_CHANGE, NOT_OFFERED_YET)

    def test_imaging_grant_is_not_collected_before_volume_ingest(self):
        with self.assertRaises(HTTPException) as caught:
            set_consent(
                ConsentIn(consent_type=NEUROIMAGING_CHANGE, granted=True),
                db=None,
                user=SimpleNamespace(id=uuid.uuid4(), role="patient"),
            )
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("data_processing does not cover", caught.exception.detail)

    def test_core_grant_does_not_authorise_imaging(self):
        with self.assertRaises(HTTPException) as caught:
            require_imaging_grant(_DenyDb(), uuid.uuid4())
        self.assertEqual(caught.exception.status_code, 403)
        self.assertIn("neuroimaging_change", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
