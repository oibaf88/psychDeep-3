import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException

from app.services.imaging_change import write_imaging_change


class ImagingChangeWriterTests(unittest.TestCase):
    def test_calls_imaging_grant_before_any_write(self):
        with self.assertRaises(HTTPException) as caught:
            write_imaging_change(object(), uuid.uuid4(), comparable_count=2, same_sequence_family=True, incidental_protocol=True)
        self.assertEqual(caught.exception.status_code, 403)
        self.assertIn("neuroimaging_change", caught.exception.detail)

    @patch("app.services.imaging_change.require_imaging_grant")
    def test_one_volume_is_not_a_change(self, _grant):
        with self.assertRaises(HTTPException) as caught:
            write_imaging_change(object(), uuid.uuid4(), comparable_count=1, same_sequence_family=True, incidental_protocol=True)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("two comparable", caught.exception.detail)

    @patch("app.services.imaging_change.require_imaging_grant")
    def test_blocked_without_incidental_protocol(self, _grant):
        with self.assertRaises(HTTPException) as caught:
            write_imaging_change(object(), uuid.uuid4(), comparable_count=2, same_sequence_family=True, incidental_protocol=False)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn("incidental-finding", caught.exception.detail)

    @patch("app.services.imaging_change.require_imaging_grant")
    def test_no_store_even_when_gates_pass(self, _grant):
        with self.assertRaises(HTTPException) as caught:
            write_imaging_change(object(), uuid.uuid4(), comparable_count=2, same_sequence_family=True, incidental_protocol=True)
        self.assertEqual(caught.exception.status_code, 501)
        self.assertIn("not written", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
