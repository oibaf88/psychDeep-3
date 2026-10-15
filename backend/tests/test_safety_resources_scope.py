"""National crisis lines are always present; local resources are explicit and labelled."""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient

from app.content.safety_resources import (
    CRISIS_RESOURCES,
    SAFETY_PROTOCOL_VERSION,
    crisis_resources,
    local_resources_label,
)
from app.main import app


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

    def test_safety_protocol_pack_is_explicitly_versioned(self):
        # Bump SAFETY_PROTOCOL_VERSION only when the reviewed pack changes.
        self.assertEqual(SAFETY_PROTOCOL_VERSION, "safety-protocol-v1")
        self.assertTrue(SAFETY_PROTOCOL_VERSION.startswith("safety-protocol-"))

    def test_resources_endpoint_exposes_protocol_version(self):
        client = TestClient(app)
        response = client.get("/api/v1/safety-plan/resources")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["protocol_version"], SAFETY_PROTOCOL_VERSION)
        self.assertEqual([item["contact"] for item in body["resources"][:2]], ["024", "112"])
        self.assertIn("safe_grounding_alternatives", body)


if __name__ == "__main__":
    unittest.main()
