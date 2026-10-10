"""National crisis lines are always present; local resources are explicit and labelled."""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app.content.safety_resources import CRISIS_RESOURCES, crisis_resources, local_resources_label


class SafetyResourcesScopeTests(unittest.TestCase):
    def test_national_lines_are_always_first_whatever_the_region(self):
        for region in ("madrid", "none", "unknown-region", "", None):
            items = crisis_resources(region) if region is not None else crisis_resources()
            self.assertEqual([item["contact"] for item in items[:2]], ["024", "112"])
            self.assertTrue(all(item["scope"] == "nacional" for item in items[:2]))

    def test_local_resources_only_with_an_explicit_region_and_labelled(self):
        self.assertEqual(len(crisis_resources("none")), 2)
        madrid = crisis_resources("madrid")
        local = [item for item in madrid if item["scope"] == "local"]
        self.assertTrue(local)
        self.assertTrue(all(item["region"] == "Comunidad de Madrid" for item in local))
        self.assertEqual(local_resources_label("madrid"), "Comunidad de Madrid")
        self.assertIsNone(local_resources_label("none"))

    def test_crisis_reply_constant_keeps_national_lines(self):
        self.assertEqual([item["contact"] for item in CRISIS_RESOURCES[:2]], ["024", "112"])


if __name__ == "__main__":
    unittest.main()
