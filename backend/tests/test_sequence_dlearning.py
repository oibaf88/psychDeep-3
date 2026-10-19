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
        self.assertTrue(hasattr(cfg["architecture"], "get") or isinstance(cfg["architecture"], dict))
        self.assertFalse(sd.requires_ml() or not HAS_TORCH)


if __name__ == "__main__":
    unittest.main()
