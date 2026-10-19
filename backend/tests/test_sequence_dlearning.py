"""Tests for the DL proposal module and its fail-closed fallback."""
import unittest

try:
    import torch  # type: ignore
    HAS_TORCH = True
except Exception:
    HAS_TORCH = False


class SequenceDLImportTests(unittest.TestCase):
    def test_module_exposes_config(self):
        from app.services import sequence_dlearning as sd

        cfg = sd.load_config()
        self.assertIn("algorithm_version", cfg)
        self.assertEqual(cfg["source_refs"], "app-only")
        self.assertEqual(sd.requires_ml(), HAS_TORCH)


if __name__ == "__main__":
    unittest.main()
