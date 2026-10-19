"""Integration checks for the optional single-patient sequence model.

These are deliberately lightweight: they do not import torch and they do not
require the ML runtime. They prove the package and the dependency manifest
are complete before a draft is merged or presented as a product change.
"""
import os
import pathlib
import unittest


def _root():
    return pathlib.Path(__file__).resolve().parents[2]


class SequenceMLPackageTests(unittest.TestCase):
    def test_dependencies_manifest_exists(self):
        manifest = _root() / "backend" / "requirements-ml.txt"
        self.assertTrue(manifest.is_file(), "requirements-ml.txt must be committed")

    def test_dependencies_are_declared(self):
        text = (_root() / "backend" / "requirements-ml.txt").read_text(encoding="utf-8")
        self.assertIn("torch", text, "torch must be declared for the optional model")
        self.assertIn("scikit-learn", text, "scikit-learn must be declared for the optional model")

    def test_module_absent_ml_is_false(self):
        import importlib

        sd = importlib.import_module("app.services.sequence_dlearning")
        self.assertFalse(sd.requires_ml(), "without torch the module must not enable ML")


if __name__ == "__main__":
    unittest.main()
