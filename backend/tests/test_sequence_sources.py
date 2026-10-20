import unittest

from app.services.sequence_sources import (
    is_external_clinical_doc,
    is_external_clinical_ref,
    sequence_refs,
)


class SequenceSourceTests(unittest.TestCase):
    def test_drops_clinical_document_refs(self):
        kept = sequence_refs([
            "chat_message:1",
            "clinical_document:abc",
            "diary_entry:2",
            "check_in:3",
        ])
        self.assertEqual(kept, ["chat_message:1", "diary_entry:2", "check_in:3"])

    def test_grant_does_not_make_a_document_ref_followable(self):
        self.assertTrue(is_external_clinical_ref("clinical_document:9"))
        self.assertFalse(is_external_clinical_ref("confirmed_fact:9"))

    def test_uploaded_report_is_not_a_sequence_doc(self):
        self.assertTrue(is_external_clinical_doc({
            "kind": "professional_clinical_document",
            "source_refs": ["clinical_document:1"],
        }))
        self.assertTrue(is_external_clinical_doc({
            "kind": "literal_chat_user",
            "source_refs": ["chat_message:1", "clinical_document:2"],
        }))
        self.assertFalse(is_external_clinical_doc({
            "kind": "literal_diary",
            "source_refs": ["diary_entry:1"],
        }))


if __name__ == "__main__":
    unittest.main()
