import inspect
import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException

from app.services.imaging_change import write_imaging_change


class ImagingChangeWriterTests(unittest.TestCase):
    def test_calls_imaging_grant_before_any_write(self):
        with self.assertRaises(HTTPException) as caught:
            write_imaging_change(object(), uuid.uuid4(), comparable_count=2, same_sequence_family=True)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertIn("neuroimaging_change", caught.exception.detail)

    @patch("app.services.imaging_change.require_imaging_grant")
    def test_one_volume_is_not_a_change(self, _grant):
        with self.assertRaises(HTTPException) as caught:
            write_imaging_change(object(), uuid.uuid4(), comparable_count=1, same_sequence_family=True)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("two comparable", caught.exception.detail)

    def test_incidental_signoff_is_not_a_client_flag(self):
        self.assertNotIn("incidental_protocol", inspect.signature(write_imaging_change).parameters)

    @patch("app.services.imaging_change.require_imaging_grant")
    def test_two_volumes_still_refuse_without_external_signoff(self, _grant):
        with self.assertRaises(HTTPException) as caught:
            write_imaging_change(object(), uuid.uuid4(), comparable_count=2, same_sequence_family=True)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("outside the app", caught.exception.detail)
        self.assertIn("not a client flag", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
